"use client";

import { useEffect, useRef, useState } from "react";

type PublicAdCampaign = {
  id: string;
  title: string;
  media_asset_id: string | null;
  target_url: string | null;
};

function track(campaignId: string, action: "impression" | "click") {
  fetch(`/api/v1/adverts/track/${campaignId}/${action}`, {
    method: "POST",
    keepalive: true,
  }).catch(() => undefined);
}

export function AdSlotBanner({ slotKey }: { slotKey: string }) {
  const [campaign, setCampaign] = useState<PublicAdCampaign | null>(null);
  const trackedId = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/v1/public/ads/${encodeURIComponent(slotKey)}`)
      .then((response) => (response.ok ? response.json() : []))
      .then((campaigns: PublicAdCampaign[]) => {
        if (cancelled || !Array.isArray(campaigns)) return;
        setCampaign(campaigns.find((item) => item.media_asset_id) ?? null);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [slotKey]);

  useEffect(() => {
    if (!campaign || trackedId.current === campaign.id) return;
    trackedId.current = campaign.id;
    track(campaign.id, "impression");
  }, [campaign]);

  if (!campaign?.media_asset_id) return null;

  const creative = (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/api/v1/public/media/${campaign.media_asset_id}`}
      alt={campaign.title}
      className="mx-auto max-h-44 w-auto rounded-md border border-line object-contain"
    />
  );

  return (
    <div className="mx-auto max-w-[82rem] px-5 py-4 text-center sm:px-6 lg:px-8">
      <p className="mb-1.5 text-[.6rem] font-bold tracking-[.18em] text-ink/45 uppercase">
        Sponsored
      </p>
      {campaign.target_url ? (
        <a
          href={campaign.target_url}
          target="_blank"
          rel="noreferrer sponsored"
          aria-label={campaign.title}
          onClick={() => track(campaign.id, "click")}
        >
          {creative}
        </a>
      ) : (
        creative
      )}
    </div>
  );
}
