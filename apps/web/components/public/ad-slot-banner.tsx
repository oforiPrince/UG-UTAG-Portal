"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";

import { publicMediaUrl } from "@/lib/public-media";

type PublicAdCampaign = {
  id: string;
  title: string;
  media_asset_id: string | null;
  target_url: string | null;
  width?: number | null;
  height?: number | null;
};

/**
 * Page-aware presentation. Each context mirrors the surrounding content column
 * so creatives stay responsive and never leave empty reserved rails.
 */
export type AdSlotContext = "home" | "listing-rail" | "article" | "footer";

type AdSlotBannerProps = {
  slotKey: string;
  context: AdSlotContext;
  className?: string;
  /** Eager-load creatives that sit near the first viewport. */
  priority?: boolean;
};

type ResolvedCreative = {
  campaign: PublicAdCampaign;
  width: number;
  height: number;
};

function track(campaignId: string, action: "impression" | "click") {
  fetch(`/api/v1/adverts/track/${campaignId}/${action}`, {
    method: "POST",
    keepalive: true,
  }).catch(() => undefined);
}

function pickCampaign(campaigns: PublicAdCampaign[], slotKey: string) {
  const live = campaigns.filter((item) => item.media_asset_id);
  if (live.length === 0) return null;
  if (live.length === 1) return live[0];
  // Stable daily rotation per placement so reloads do not flicker.
  const day = new Date().toISOString().slice(0, 10);
  let hash = 0;
  const seed = `${slotKey}:${day}`;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) >>> 0;
  }
  return live[hash % live.length] ?? live[0];
}

function contextDefaults(context: AdSlotContext) {
  switch (context) {
    case "home":
      return {
        maxWidth: 970,
        shell:
          "public-ad public-ad--home mx-auto w-full min-w-0 max-w-[82rem] px-4 py-6 sm:px-6 sm:py-7 lg:px-8",
        frame: "public-ad__frame public-ad__frame--strip",
        label: "Sponsored",
      };
    case "listing-rail":
      return {
        maxWidth: 300,
        shell:
          "public-ad public-ad--rail mx-auto w-full min-w-0 max-w-[300px] lg:mx-0 lg:w-[300px] lg:sticky lg:top-24",
        frame: "public-ad__frame public-ad__frame--rail",
        label: "Sponsored",
      };
    case "article":
      return {
        maxWidth: 728,
        shell:
          "public-ad public-ad--article mx-auto w-full min-w-0 max-w-4xl px-4 py-6 sm:px-6",
        frame: "public-ad__frame public-ad__frame--inline",
        label: "Sponsored",
      };
    case "footer":
      return {
        maxWidth: 970,
        shell:
          "public-ad public-ad--footer mx-auto w-full min-w-0 max-w-[82rem] px-4 py-5 sm:px-6 lg:px-8",
        frame: "public-ad__frame public-ad__frame--footer",
        label: "Sponsored",
      };
  }
}

export function AdSlotBanner({
  slotKey,
  context,
  className = "",
  priority = false,
}: AdSlotBannerProps) {
  const [creative, setCreative] = useState<ResolvedCreative | null>(null);
  const [visible, setVisible] = useState(false);
  const rootRef = useRef<HTMLElement | null>(null);
  const impressionTracked = useRef<string | null>(null);
  const defaults = contextDefaults(context);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/v1/public/ads/${encodeURIComponent(slotKey)}`)
      .then((response) => (response.ok ? response.json() : []))
      .then((campaigns: PublicAdCampaign[]) => {
        if (cancelled || !Array.isArray(campaigns)) return;
        const next = pickCampaign(campaigns, slotKey);
        if (!next?.media_asset_id || !next.width || !next.height) {
          setCreative(null);
          return;
        }
        setCreative({
          campaign: next,
          width: next.width,
          height: next.height,
        });
      })
      .catch(() => {
        if (!cancelled) setCreative(null);
      });
    return () => {
      cancelled = true;
    };
  }, [slotKey]);

  useEffect(() => {
    const node = rootRef.current;
    if (!node || !creative) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.45)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: [0, 0.45, 0.75], rootMargin: "40px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [creative]);

  useEffect(() => {
    if (!creative || !visible) return;
    if (impressionTracked.current === creative.campaign.id) return;
    impressionTracked.current = creative.campaign.id;
    track(creative.campaign.id, "impression");
  }, [creative, visible]);

  if (!creative) return null;

  const maxWidth = Math.min(creative.width, defaults.maxWidth);
  const creativeNode = (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={
        publicMediaUrl(creative.campaign.media_asset_id, "w960") ??
        `/api/v1/public/media/${creative.campaign.media_asset_id}`
      }
      alt={creative.campaign.title}
      width={creative.width}
      height={creative.height}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      fetchPriority={priority ? "high" : "auto"}
      sizes={
        context === "listing-rail"
          ? "300px"
          : context === "article"
            ? "(max-width: 896px) 100vw, 728px"
            : "(max-width: 970px) 100vw, 970px"
      }
      className="public-ad__creative"
    />
  );

  return (
    <aside
      ref={rootRef}
      className={`${defaults.shell} ${className}`.trim()}
      aria-label="Advertisement"
      data-ad-slot={slotKey}
      data-ad-context={context}
      data-ready={visible ? "true" : "false"}
      style={
        {
          "--ad-max-width": `${maxWidth}px`,
          "--ad-aspect": `${creative.width} / ${creative.height}`,
        } as CSSProperties
      }
    >
      <div className="public-ad__label-row">
        <p className="public-ad__label">{defaults.label}</p>
      </div>
      <div className={defaults.frame}>
        {creative.campaign.target_url ? (
          <a
            href={creative.campaign.target_url}
            target="_blank"
            rel="noreferrer sponsored noopener"
            aria-label={creative.campaign.title}
            className="public-ad__link"
            onClick={() => track(creative.campaign.id, "click")}
          >
            {creativeNode}
          </a>
        ) : (
          creativeNode
        )}
      </div>
    </aside>
  );
}
