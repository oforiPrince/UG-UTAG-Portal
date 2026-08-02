"use client";

import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  ImageIcon,
  LoaderCircle,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { WorkspaceField } from "@/lib/workspaces";

type MediaAsset = {
  id: string;
  original_filename: string;
  content_type: string;
  status: string;
  is_private: boolean;
  alt_text: string | null;
};

const IMAGE_TYPES = [
  "image/avif",
  "image/gif",
  "image/jpeg",
  "image/png",
  "image/webp",
];

const DOCUMENT_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/csv",
  "text/plain",
];

const MAX_UPLOAD_BYTES = 25_000_000;

type QueuedFile = { file: File; previewUrl: string };

function queueFile(file: File): QueuedFile {
  return {
    file,
    previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : "",
  };
}

function revokePreviews(items: QueuedFile[]) {
  for (const item of items) {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  }
}

function acceptedTypes(field: WorkspaceField) {
  if (field.media?.accept === "image") return IMAGE_TYPES;
  if (field.media?.accept === "document") return DOCUMENT_TYPES;
  return [...IMAGE_TYPES, ...DOCUMENT_TYPES];
}

function selectedIds(field: WorkspaceField, value: string | string[]) {
  if (field.media?.multiple) return Array.isArray(value) ? value : [];
  return Array.isArray(value) ? value.slice(0, 1) : value ? [value] : [];
}

function previewClass(field: WorkspaceField) {
  if (field.media?.aspect === "portrait") return "aspect-[4/5]";
  if (field.media?.aspect === "square") return "aspect-square";
  return "aspect-[16/8]";
}

async function waitForScan(assetId: string) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const asset = await api<MediaAsset>(`/api/v1/media/${assetId}`);
    if (asset.status === "ready") return asset;
    if (["rejected", "archived"].includes(asset.status)) {
      throw new Error(
        asset.status === "rejected"
          ? "The uploaded file did not pass security or image validation"
          : "The uploaded file is no longer available",
      );
    }
    await new Promise((resolve) => window.setTimeout(resolve, 750));
  }
  throw new Error(
    "The upload is still being checked. It is saved in Media and can be selected when ready.",
  );
}

function SelectedAsset({
  asset,
  assetId,
  field,
  remove,
  allowDownload,
  onAllowDownloadChange,
}: {
  asset?: MediaAsset;
  assetId: string;
  field: WorkspaceField;
  remove: () => void;
  allowDownload?: boolean;
  onAllowDownloadChange?: (allowed: boolean) => void;
}) {
  const isImage =
    asset?.content_type.startsWith("image/") || field.media?.accept === "image";
  return (
    <div className="group relative overflow-hidden rounded-xl border border-line bg-panel">
      {isImage ? (
        <div
          className={`relative overflow-hidden bg-ink/5 ${previewClass(field)}`}
        >
          <Image
            fill
            unoptimized
            alt={asset?.alt_text || asset?.original_filename || field.label}
            className="object-cover"
            sizes="(min-width: 640px) 280px, 100vw"
            src={`/api/v1/media/${assetId}/content`}
          />
        </div>
      ) : (
        <div className="flex min-h-24 items-center gap-3 p-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-sky/10 text-sky">
            <FileText className="size-5" />
          </span>
          <span className="min-w-0">
            <b className="block truncate text-xs">
              {asset?.original_filename ?? "Selected file"}
            </b>
            <span className="mt-1 block text-[.62rem] font-normal text-muted">
              Ready to use
            </span>
          </span>
        </div>
      )}
      <button
        type="button"
        onClick={remove}
        aria-label={`Remove ${asset?.original_filename ?? field.label}`}
        className="absolute top-2 right-2 grid size-8 place-items-center rounded-full bg-paper/95 text-ink shadow-md transition hover:bg-red-700 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink/30"
      >
        <X className="size-4" />
      </button>
      {isImage ? (
        <div className="grid gap-2 border-t border-line px-3 py-2">
          <p className="truncate text-[.65rem] font-bold">
            {asset?.original_filename ?? "Selected image"}
          </p>
          {onAllowDownloadChange ? (
            <label className="flex items-center gap-2 text-[.62rem] font-normal text-muted">
              <input
                type="checkbox"
                checked={allowDownload !== false}
                onChange={(event) =>
                  onAllowDownloadChange(event.target.checked)
                }
                className="size-3.5 rounded border-line accent-sky"
              />
              Allow public download
            </label>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function WorkspaceMediaField({
  field,
  value,
  onChange,
  onBusyChange,
  picker,
  downloadBlockedIds,
  onDownloadBlockedChange,
}: {
  field: WorkspaceField;
  value: string | string[];
  onChange: (value: string | string[]) => void;
  onBusyChange?: (busy: boolean) => void;
  picker?: React.ReactNode;
  downloadBlockedIds?: string[];
  onDownloadBlockedChange?: (ids: string[]) => void;
}) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const queueRef = useRef<QueuedFile[]>([]);
  const [altText, setAltText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploaded, setUploaded] = useState(0);
  const allowMultiple = Boolean(field.media?.multiple);
  const ids = selectedIds(field, value);
  const assetQueries = useQueries({
    queries: ids.map((assetId) => ({
      queryKey: ["workspace-media-preview", assetId],
      queryFn: () => api<MediaAsset>(`/api/v1/media/${assetId}`),
      staleTime: 30_000,
    })),
  });
  const assetMap = new Map(
    assetQueries.flatMap((query) =>
      query.data ? [[query.data.id, query.data] as const] : [],
    ),
  );
  const accepts = acceptedTypes(field);

  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  useEffect(() => () => revokePreviews(queueRef.current), []);

  function clearQueue() {
    revokePreviews(queueRef.current);
    setQueue([]);
    setAltText("");
    setUploaded(0);
    if (input.current) input.current.value = "";
  }

  const upload = useMutation({
    mutationFn: async (selected: File[]) => {
      const assets: MediaAsset[] = [];
      const failures: string[] = [];
      // Uploads run one at a time so each file clears malware scanning before the next.
      for (const current of selected) {
        try {
          const form = new FormData();
          form.append("file", current);
          form.append("is_private", String(field.media?.isPrivate ?? false));
          if (selected.length === 1 && altText.trim()) {
            form.append("alt_text", altText.trim());
          }
          const pending = await api<MediaAsset>("/api/v1/media/upload", {
            method: "POST",
            body: form,
          });
          assets.push(await waitForScan(pending.id));
        } catch (error) {
          failures.push(
            `${current.name}: ${error instanceof Error ? error.message : "upload failed"}`,
          );
        }
        setUploaded((count) => count + 1);
      }
      if (!assets.length) {
        throw new Error(failures.join(" · ") || "The file could not be uploaded");
      }
      return { assets, failures };
    },
    onMutate: () => {
      setUploaded(0);
      onBusyChange?.(true);
    },
    onSuccess: async ({ assets, failures }) => {
      const next = allowMultiple
        ? [...new Set([...ids, ...assets.map((asset) => asset.id)])]
        : assets[0].id;
      onChange(next);
      clearQueue();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workspace-options"] }),
        queryClient.invalidateQueries({
          queryKey: ["workspace-media-preview"],
        }),
        queryClient.invalidateQueries({ queryKey: ["media"] }),
      ]);
      toast.success(
        assets.length === 1
          ? `${assets[0].original_filename} is ready and selected`
          : `${assets.length} files are ready and selected`,
      );
      for (const failure of failures) toast.error(failure);
    },
    onError: (error) =>
      toast.error(
        error instanceof Error
          ? error.message
          : "The file could not be uploaded",
      ),
    onSettled: () => onBusyChange?.(false),
  });

  function choose(fileList: FileList | null) {
    const incoming = Array.from(fileList ?? []);
    if (!incoming.length) return;
    const candidates = allowMultiple ? incoming : incoming.slice(0, 1);
    const accepted: File[] = [];
    for (const candidate of candidates) {
      if (!accepts.includes(candidate.type)) {
        toast.error(
          field.media?.accept === "image"
            ? `${candidate.name} is not a JPG, PNG, WebP, GIF, or AVIF image`
            : `${candidate.name} is not a supported file type`,
        );
        continue;
      }
      if (candidate.size > MAX_UPLOAD_BYTES) {
        toast.error(`${candidate.name} is larger than 25 MB`);
        continue;
      }
      accepted.push(candidate);
    }
    if (!accepted.length) return;
    const kept = allowMultiple ? queueRef.current : [];
    if (!allowMultiple) revokePreviews(queueRef.current);
    const next = [...kept];
    for (const candidate of accepted) {
      const duplicate = next.some(
        (item) =>
          item.file.name === candidate.name && item.file.size === candidate.size,
      );
      if (!duplicate) next.push(queueFile(candidate));
    }
    setQueue(next);
  }

  function removeQueued(index: number) {
    const target = queueRef.current[index];
    if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
    setQueue(queueRef.current.filter((_, position) => position !== index));
    if (input.current) input.current.value = "";
  }

  function remove(assetId: string) {
    onChange(allowMultiple ? ids.filter((current) => current !== assetId) : "");
    if (onDownloadBlockedChange && downloadBlockedIds) {
      onDownloadBlockedChange(
        downloadBlockedIds.filter((current) => current !== assetId),
      );
    }
  }

  function setAllowDownload(assetId: string, allowed: boolean) {
    if (!onDownloadBlockedChange) return;
    const blocked = new Set(downloadBlockedIds ?? []);
    if (allowed) blocked.delete(assetId);
    else blocked.add(assetId);
    onDownloadBlockedChange(
      ids.filter((current) => blocked.has(current)),
    );
  }

  const singleImageQueued =
    queue.length === 1 && queue[0].file.type.startsWith("image/");
  const downloadControl = Boolean(
    field.media?.downloadControl && onDownloadBlockedChange,
  );
  const blockedSet = new Set(downloadBlockedIds ?? []);

  return (
    <div className="grid gap-4">
      {ids.length ? (
        <div
          className={
            allowMultiple ? "grid gap-3 sm:grid-cols-2" : "grid max-w-md gap-3"
          }
        >
          {ids.map((assetId) => (
            <SelectedAsset
              key={assetId}
              assetId={assetId}
              asset={assetMap.get(assetId)}
              field={field}
              remove={() => remove(assetId)}
              allowDownload={downloadControl ? !blockedSet.has(assetId) : undefined}
              onAllowDownloadChange={
                downloadControl
                  ? (allowed) => setAllowDownload(assetId, allowed)
                  : undefined
              }
            />
          ))}
        </div>
      ) : (
        <div className="flex min-h-24 items-center justify-center gap-3 rounded-xl border border-dashed border-line bg-ink/[.018] px-5 text-center text-xs font-normal text-muted">
          {field.media?.accept === "image" ? (
            <ImageIcon className="size-5 shrink-0" />
          ) : (
            <FileText className="size-5 shrink-0" />
          )}
          No {allowMultiple ? "files" : "image"} selected yet
        </div>
      )}

      {queue.length ? (
        <div className="overflow-hidden rounded-2xl border border-sky/30 bg-sky/[.035]">
          <div
            className={
              queue.length === 1
                ? "grid gap-4 p-4 sm:grid-cols-[8rem_1fr] sm:items-center"
                : "grid gap-3 p-4 sm:grid-cols-3"
            }
          >
            {queue.map((item, index) => (
              <div
                key={`${item.file.name}-${item.file.size}`}
                className={
                  queue.length === 1 ? "" : "relative min-w-0 text-center"
                }
              >
                {item.previewUrl ? (
                  <div className="relative aspect-square overflow-hidden rounded-xl bg-ink/5">
                    <Image
                      fill
                      unoptimized
                      alt={`Preview of ${item.file.name}`}
                      className="object-cover"
                      src={item.previewUrl}
                    />
                  </div>
                ) : (
                  <div className="grid aspect-square place-items-center rounded-xl bg-paper">
                    <FileText className="size-7 text-sky" />
                  </div>
                )}
                {queue.length > 1 ? (
                  <>
                    <button
                      type="button"
                      disabled={upload.isPending}
                      onClick={() => removeQueued(index)}
                      aria-label={`Remove ${item.file.name} from this upload`}
                      className="absolute top-1.5 right-1.5 grid size-7 place-items-center rounded-full bg-paper/95 text-ink shadow-md transition hover:bg-red-700 hover:text-white disabled:opacity-50"
                    >
                      <X className="size-3.5" />
                    </button>
                    <p className="mt-1.5 truncate text-[.62rem] font-bold">
                      {item.file.name}
                    </p>
                  </>
                ) : null}
              </div>
            ))}
            {queue.length === 1 ? (
              <div className="min-w-0">
                <b className="block truncate text-sm">{queue[0].file.name}</b>
                <span className="mt-1 block text-[.65rem] font-normal text-muted">
                  {(queue[0].file.size / 1_000_000).toFixed(2)} MB · Preview
                  before upload
                </span>
                {singleImageQueued ? (
                  <label className="mt-3 grid gap-1.5 text-[.65rem] font-bold">
                    Alternative text
                    <input
                      value={altText}
                      maxLength={500}
                      onChange={(event) => setAltText(event.target.value)}
                      placeholder="Describe the image for screen readers"
                      className="min-h-10 rounded-lg border border-line bg-paper px-3 text-xs font-normal outline-none focus:border-ink/25"
                    />
                  </label>
                ) : null}
              </div>
            ) : null}
          </div>
          {queue.length > 1 ? (
            <p className="border-t border-line px-4 py-2.5 text-[.62rem] font-normal text-muted">
              {queue.length} files queued. Add alternative text for each image
              in the Media library after upload.
            </p>
          ) : null}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
            <span className="inline-flex items-center gap-2 text-[.62rem] font-normal text-muted">
              <ShieldCheck className="size-4 text-emerald-600" />
              Security scanning happens automatically
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={upload.isPending}
                onClick={clearQueue}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={upload.isPending}
                onClick={() => upload.mutate(queue.map((item) => item.file))}
              >
                {upload.isPending ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <UploadCloud className="size-4" />
                )}
                {upload.isPending
                  ? queue.length > 1
                    ? `Scanning ${Math.min(uploaded + 1, queue.length)} of ${queue.length}…`
                    : "Scanning…"
                  : queue.length > 1
                    ? `Upload ${queue.length} files`
                    : "Upload and use"}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <>
          <button
            type="button"
            className={`grid min-h-28 place-items-center rounded-xl border-2 border-dashed px-5 py-4 text-center transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink/30 ${
              dragging
                ? "border-coral bg-coral/5"
                : "border-line hover:border-sky hover:bg-sky/[.025]"
            }`}
            onClick={() => input.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              choose(event.dataTransfer.files);
            }}
          >
            <span>
              <UploadCloud className="mx-auto size-6 text-coral" />
              <b className="mt-2 block text-xs">Upload from this form</b>
              <span className="mt-1 block text-[.62rem] font-normal text-muted">
                {allowMultiple
                  ? "Drop files here or choose several from your device · up to 25 MB each"
                  : "Drop a file here or choose from your device · up to 25 MB"}
              </span>
            </span>
          </button>
          <input
            ref={input}
            type="file"
            multiple={allowMultiple}
            className="sr-only"
            accept={accepts.join(",")}
            onChange={(event) => choose(event.target.files)}
          />
        </>
      )}

      {picker ? (
        <div className="grid gap-2 border-t border-line pt-4">
          <span className="text-[.65rem] font-black tracking-wide text-muted uppercase">
            Or choose an existing ready file
          </span>
          {picker}
        </div>
      ) : null}
    </div>
  );
}
