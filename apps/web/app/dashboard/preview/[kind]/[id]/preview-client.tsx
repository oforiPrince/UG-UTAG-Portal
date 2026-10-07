"use client";
/* eslint-disable @next/next/no-img-element */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, FileWarning, LoaderCircle } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { humanize } from "@/lib/utils";

type ModerationPreview = {
  id: string;
  kind: "news" | "announcement" | "event" | "document" | "gallery";
  title: string;
  summary: string;
  body_html: string;
  status: string;
  media_asset_ids: string[];
  details: Record<string, string>;
};

const workspaceUrls: Record<ModerationPreview["kind"], string> = {
  news: "/dashboard/news",
  announcement: "/dashboard/announcements",
  event: "/dashboard/events",
  document: "/dashboard/documents",
  gallery: "/dashboard/galleries",
};

export function ModerationPreviewClient({
  kind,
  id,
}: {
  kind: string;
  id: string;
}) {
  const validKind = Object.hasOwn(workspaceUrls, kind)
    ? (kind as ModerationPreview["kind"])
    : null;
  const preview = useQuery({
    queryKey: ["moderation", "preview", kind, id],
    queryFn: () =>
      api<ModerationPreview>(
        `/api/v1/moderation/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/preview`,
      ),
    enabled: Boolean(validKind),
  });

  if (!validKind) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <FileWarning className="mx-auto size-8 text-coral" />
          <h1 className="mt-4 text-xl font-black">
            This preview type is not supported.
          </h1>
        </CardContent>
      </Card>
    );
  }

  if (preview.isLoading) {
    return (
      <div className="grid min-h-72 place-items-center">
        <LoaderCircle
          className="size-8 animate-spin text-coral"
          aria-label="Loading preview"
        />
      </div>
    );
  }

  if (!preview.data || preview.error) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <FileWarning className="mx-auto size-8 text-coral" />
          <h1 className="mt-4 text-xl font-black">
            The preview could not be loaded.
          </h1>
          <Button asChild className="mt-6" variant="outline">
            <Link href={workspaceUrls[validKind]}>Back to workspace</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const item = preview.data;
  const heroMediaId =
    item.kind === "news" || item.kind === "event"
      ? item.media_asset_ids[0]
      : undefined;

  return (
    <article className="overflow-hidden rounded-3xl border border-line bg-panel shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gold/30 bg-[#172f4d] px-5 py-3 text-white sm:px-8">
        <p className="text-xs font-bold">
          Private preview · {humanize(item.kind)} · {humanize(item.status)}
        </p>
        <div className="flex gap-2">
          <Button
            asChild
            size="sm"
            variant="outline"
            className="border-white/30 bg-transparent text-white"
          >
            <Link href="/dashboard/moderation">
              <ArrowLeft className="size-4" /> Moderation
            </Link>
          </Button>
          <Button
            asChild
            size="sm"
            className="bg-gold text-[#172f4d] hover:bg-gold/90"
          >
            <Link href={workspaceUrls[item.kind]}>Edit content</Link>
          </Button>
        </div>
      </div>

      <header className="relative isolate overflow-hidden bg-[#102a48] px-6 py-14 text-white sm:px-10 sm:py-18">
        {heroMediaId ? (
          <img
            src={`/api/v1/media/${heroMediaId}/content`}
            alt=""
            className="absolute inset-0 -z-20 size-full object-cover"
          />
        ) : null}
        <div className="absolute inset-0 -z-10 bg-[#102a48]/90" />
        <p className="text-[.68rem] font-black tracking-[.14em] text-gold uppercase">
          {humanize(item.kind)}
        </p>
        <h1 className="display-type mt-4 max-w-5xl text-4xl leading-tight sm:text-6xl">
          {item.title}
        </h1>
        {item.summary ? (
          <p className="mt-5 max-w-3xl text-sm leading-7 text-white/72 sm:text-base">
            {item.summary}
          </p>
        ) : null}
      </header>

      <div className="grid gap-8 p-6 sm:p-10 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div>
          {item.kind === "gallery" ? (
            item.media_asset_ids.length ? (
              <div className="columns-1 gap-4 sm:columns-2">
                {item.media_asset_ids.map((assetId, index) => (
                  <img
                    key={assetId}
                    src={`/api/v1/media/${assetId}/content`}
                    alt={`${item.title} preview image ${index + 1}`}
                    className="mb-4 w-full break-inside-avoid rounded-xl"
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">
                No gallery images have been selected.
              </p>
            )
          ) : item.kind === "document" ? (
            item.media_asset_ids[0] ? (
              <Button asChild>
                <a
                  href={`/api/v1/media/${item.media_asset_ids[0]}/content`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Download className="size-4" /> Open document
                </a>
              </Button>
            ) : (
              <p className="text-sm text-muted">
                No document file is attached.
              </p>
            )
          ) : item.body_html ? (
            <div
              className="themed-prose max-w-none"
              dangerouslySetInnerHTML={{ __html: item.body_html }}
            />
          ) : (
            <p className="text-sm text-muted">
              No body content has been added.
            </p>
          )}
        </div>

        <aside className="h-fit rounded-2xl border border-line bg-paper p-5">
          <p className="text-[.65rem] font-black tracking-wide text-muted uppercase">
            Content details
          </p>
          <dl className="mt-4 grid gap-4">
            {Object.entries(item.details).map(([label, value]) => (
              <div key={label} className="border-t border-line pt-3">
                <dt className="text-[.62rem] font-bold text-muted uppercase">
                  {label}
                </dt>
                <dd className="mt-1 text-sm font-semibold">
                  {humanize(value)}
                </dd>
              </div>
            ))}
          </dl>
        </aside>
      </div>
    </article>
  );
}
