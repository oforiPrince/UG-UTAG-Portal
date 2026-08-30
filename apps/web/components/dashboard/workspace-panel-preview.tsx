"use client";

import { useQuery } from "@tanstack/react-query";
import { FileWarning, LoaderCircle } from "lucide-react";

import { DocumentPreview } from "@/components/documents/document-preview";
import { api } from "@/lib/api";
import { type MemberDocument, memberDocumentPreview } from "@/lib/documents";
import { humanize } from "@/lib/utils";
import type { WorkspacePreviewKind, WorkspaceRow } from "@/lib/workspaces";

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

function DocumentPanelPreview({
  id,
  onBack,
}: {
  id: string;
  onBack: () => void;
}) {
  const document = useQuery({
    queryKey: ["documents", "preview", id],
    queryFn: () =>
      api<MemberDocument>(`/api/v1/documents/${encodeURIComponent(id)}`),
    retry: false,
  });

  if (document.isLoading) {
    return (
      <div className="grid min-h-64 place-items-center">
        <LoaderCircle
          className="size-7 animate-spin text-coral"
          aria-label="Loading document preview"
        />
      </div>
    );
  }

  if (!document.data || document.error) {
    return (
      <div className="rounded-xl border border-line bg-panel px-5 py-10 text-center">
        <FileWarning className="mx-auto size-8 text-coral" />
        <p className="mt-3 text-sm font-black">
          This document preview could not be loaded.
        </p>
        <p className="mt-2 text-xs leading-5 text-muted">
          The document may no longer be available, or its files may still be
          completing security checks.
        </p>
      </div>
    );
  }

  return (
    <DocumentPreview
      document={memberDocumentPreview(document.data)}
      privateView
      embedded
      onBack={onBack}
      backLabel="Back to details"
    />
  );
}

function NewsPanelPreview({ id, onBack }: { id: string; onBack: () => void }) {
  const preview = useQuery({
    queryKey: ["moderation", "preview", "news", id],
    queryFn: () =>
      api<ModerationPreview>(
        `/api/v1/moderation/news/${encodeURIComponent(id)}/preview`,
      ),
  });

  if (preview.isLoading) {
    return (
      <div className="grid min-h-64 place-items-center">
        <LoaderCircle
          className="size-7 animate-spin text-coral"
          aria-label="Loading article preview"
        />
      </div>
    );
  }

  if (!preview.data || preview.error) {
    return (
      <div className="rounded-xl border border-line bg-panel px-5 py-10 text-center">
        <FileWarning className="mx-auto size-8 text-coral" />
        <p className="mt-3 text-sm font-black">
          This article preview could not be loaded.
        </p>
      </div>
    );
  }

  const item = preview.data;
  const heroMediaId = item.media_asset_ids[0];

  return (
    <article className="overflow-hidden rounded-md border border-line bg-paper">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-[#172f4d] px-4 py-3 text-white">
        <p className="text-xs font-bold">
          Private preview · {humanize(item.kind)} · {humanize(item.status)}
        </p>
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-white/25 px-3 py-1.5 text-xs font-bold hover:bg-white/10"
        >
          Back to details
        </button>
      </div>
      <header className="relative isolate overflow-hidden bg-[#102a48] px-5 py-10 text-white">
        {heroMediaId ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`/api/v1/media/${heroMediaId}/content`}
            alt=""
            className="absolute inset-0 -z-20 size-full object-cover"
          />
        ) : null}
        <div className="absolute inset-0 -z-10 bg-[#102a48]/90" />
        <h2 className="display-type max-w-3xl text-3xl leading-tight">
          {item.title}
        </h2>
        {item.summary ? (
          <p className="mt-4 max-w-2xl text-sm leading-6 text-white/72">
            {item.summary}
          </p>
        ) : null}
      </header>
      <div className="p-5">
        {item.body_html ? (
          <div
            className="themed-prose max-w-none text-sm"
            dangerouslySetInnerHTML={{ __html: item.body_html }}
          />
        ) : (
          <p className="text-sm text-muted">No body content has been added.</p>
        )}
        {Object.keys(item.details).length ? (
          <dl className="mt-8 divide-y divide-line border-t border-line">
            {Object.entries(item.details).map(([label, value]) => (
              <div
                key={label}
                className="grid gap-1 py-3 sm:grid-cols-[7.5rem_1fr] sm:gap-3"
              >
                <dt className="text-[.65rem] font-black tracking-wide text-muted uppercase">
                  {label}
                </dt>
                <dd className="text-xs font-semibold">{humanize(value)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </article>
  );
}

export function WorkspacePanelPreview({
  kind,
  row,
  onBack,
}: {
  kind: WorkspacePreviewKind;
  row: WorkspaceRow;
  onBack: () => void;
}) {
  const id = String(row.id ?? "");
  if (!id) {
    return (
      <div className="rounded-xl border border-line bg-panel px-5 py-10 text-center">
        <p className="text-sm font-black">Preview is unavailable.</p>
      </div>
    );
  }
  if (kind === "document") {
    return <DocumentPanelPreview id={id} onBack={onBack} />;
  }
  return <NewsPanelPreview id={id} onBack={onBack} />;
}
