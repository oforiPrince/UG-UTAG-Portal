"use client";

import {
  ArrowDownToLine,
  ArrowUpRight,
  ChevronDown,
  ExternalLink,
  FileImage,
  FileText,
} from "lucide-react";
import { useId, useState } from "react";

import { documentPreviewKind, fileSize } from "@/lib/documents";

export type PublicAttachment = {
  media_asset_id: string;
  filename: string;
  content_type: string;
  byte_size?: number;
  content_url: string;
};

function friendlyName(filename: string) {
  const base = filename.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
  if (!base) return filename;
  return base.replace(/\s+/g, " ");
}

function AttachmentIcon({ contentType }: { contentType: string }) {
  const kind = documentPreviewKind(contentType);
  if (kind === "image") return <FileImage className="size-5" aria-hidden />;
  return <FileText className="size-5" aria-hidden />;
}

function AttachmentViewer({ attachment }: { attachment: PublicAttachment }) {
  const kind = documentPreviewKind(attachment.content_type);
  const label = friendlyName(attachment.filename);

  if (kind === "pdf" || kind === "text") {
    return (
      <div className="relative bg-[#e8eef4]">
        <iframe
          src={
            kind === "pdf"
              ? `${attachment.content_url}#view=FitH`
              : attachment.content_url
          }
          title={`Preview of ${label}`}
          className="block h-[min(78vh,52rem)] w-full border-0 bg-white"
        />
      </div>
    );
  }

  if (kind === "image") {
    return (
      <div className="bg-[#e8eef4] p-3 sm:p-5">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={attachment.content_url}
          alt={label}
          className="mx-auto max-h-[min(78vh,52rem)] w-auto max-w-full object-contain shadow-[0_12px_40px_rgb(23_43_69_/_16%)]"
          loading="lazy"
          decoding="async"
        />
      </div>
    );
  }

  return (
    <div className="grid min-h-48 place-items-center bg-[#f3f6fa] px-6 py-12 text-center">
      <div className="max-w-sm">
        <span className="mx-auto grid size-12 place-items-center rounded-full bg-white text-coral shadow-sm">
          <AttachmentIcon contentType={attachment.content_type} />
        </span>
        <p className="mt-4 text-sm font-bold text-[#172f4d]">
          Inline preview is not available for this file type
        </p>
        <p className="mt-2 text-sm leading-6 text-muted">
          Open it in a new tab to read it in your browser without downloading.
        </p>
        <a
          href={attachment.content_url}
          target="_blank"
          rel="noreferrer"
          className="mt-5 inline-flex items-center gap-2 rounded-md bg-[#172f4d] px-4 py-2.5 text-xs font-extrabold text-white transition hover:bg-coral"
        >
          <ExternalLink className="size-4" />
          Open to read
        </a>
      </div>
    </div>
  );
}

function AttachmentCard({
  attachment,
  defaultOpen,
  index,
}: {
  attachment: PublicAttachment;
  defaultOpen: boolean;
  index: number;
}) {
  const panelId = useId();
  const [open, setOpen] = useState(defaultOpen);
  const kind = documentPreviewKind(attachment.content_type);
  const label = friendlyName(attachment.filename);
  const typeLabel =
    kind === "pdf"
      ? "PDF"
      : kind === "image"
        ? "Image"
        : kind === "text"
          ? "Text"
          : attachment.content_type.split("/").pop()?.toUpperCase() || "File";
  const sizeLabel =
    typeof attachment.byte_size === "number" && attachment.byte_size > 0
      ? fileSize(attachment.byte_size)
      : null;

  return (
    <article className="overflow-hidden rounded-md border border-line bg-white shadow-[0_10px_36px_rgb(23_43_69_/_8%)]">
      <div className="flex flex-col gap-3 border-b border-line bg-[#172f4d] px-4 py-4 text-white sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-full bg-white/10 text-gold">
            <AttachmentIcon contentType={attachment.content_type} />
          </span>
          <div className="min-w-0">
            <p className="text-[.62rem] font-extrabold tracking-[.14em] text-gold uppercase">
              Document {index + 1} · {typeLabel}
            </p>
            <h3 className="mt-1 truncate text-sm font-bold sm:text-base">
              {label}
            </h3>
            <p className="mt-1 text-xs text-white/60">
              {[sizeLabel, attachment.filename !== label ? attachment.filename : null]
                .filter(Boolean)
                .join(" · ") || "Ready to read online"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          <a
            href={attachment.content_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-md border border-white/20 bg-white/5 px-3 py-2 text-xs font-bold text-white transition hover:bg-white/12"
          >
            <ArrowUpRight className="size-3.5" />
            Open
          </a>
          <a
            href={attachment.content_url}
            download={attachment.filename}
            className="inline-flex items-center gap-2 rounded-md bg-gold px-3 py-2 text-xs font-extrabold text-[#172f4d] transition hover:bg-[#e0b640]"
          >
            <ArrowDownToLine className="size-3.5" />
            Download
          </a>
          <button
            type="button"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((value) => !value)}
            className="inline-flex items-center gap-2 rounded-md border border-white/20 bg-transparent px-3 py-2 text-xs font-bold text-white transition hover:bg-white/12"
          >
            <ChevronDown
              className={`size-3.5 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
            />
            {open ? "Hide" : "Show"}
          </button>
        </div>
      </div>
      {open ? (
        <div id={panelId}>
          <AttachmentViewer attachment={attachment} />
        </div>
      ) : null}
    </article>
  );
}

export function PublicAttachments({
  attachments,
  eyebrow = "Accompanying files",
  title = "Supporting documents",
  description,
  id = "documents",
}: {
  attachments: PublicAttachment[];
  eyebrow?: string;
  title?: string;
  description?: string;
  id?: string;
}) {
  if (!attachments.length) return null;

  const headingId = `${id}-heading`;
  const intro =
    description ??
    (attachments.length === 1
      ? "The document below opens here so you can read it without downloading."
      : "These documents open here by default so you can read them without downloading.");

  return (
    <section
      aria-labelledby={headingId}
      className="scroll-mt-24"
      id={id}
    >
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-4">
        <div>
          <p className="text-[.68rem] font-extrabold tracking-[.14em] text-coral uppercase">
            {eyebrow}
          </p>
          <h2
            id={headingId}
            className="mt-2 text-2xl font-black tracking-tight text-[#172f4d]"
          >
            {title}
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted">{intro}</p>
        </div>
        <p className="text-xs font-bold text-muted">
          {attachments.length} file{attachments.length === 1 ? "" : "s"}
        </p>
      </div>
      <div className="mt-6 grid gap-5">
        {attachments.map((attachment, index) => (
          <AttachmentCard
            key={attachment.media_asset_id}
            attachment={attachment}
            defaultOpen
            index={index}
          />
        ))}
      </div>
    </section>
  );
}
