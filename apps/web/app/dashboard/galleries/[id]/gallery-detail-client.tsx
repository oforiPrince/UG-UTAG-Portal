"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarClock,
  Download,
  ExternalLink,
  ImageIcon,
  Link2,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { WorkspaceRichTextValue } from "@/components/dashboard/workspace-rich-text-value";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PortalApiError, api } from "@/lib/api";
import { galleryDetailQueryKey, type DashboardGallery } from "@/lib/galleries";
import { workspaces } from "@/lib/workspaces";
import { cn, humanize } from "@/lib/utils";

type User = { permissions: string[] };

function formatDateTime(value: string | null) {
  if (!value) return "Not published";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en-GH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function GalleryDetailsLoading() {
  return (
    <div className="grid animate-pulse gap-5" aria-label="Loading gallery">
      <div className="h-10 w-44 rounded-full bg-ink/5" />
      <div className="h-24 max-w-2xl rounded-2xl bg-ink/5" />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="aspect-[16/9] rounded-[1.35rem] bg-ink/5" />
        <div className="h-80 rounded-[1.35rem] bg-ink/5" />
      </div>
    </div>
  );
}

function GalleryLoadError({
  error,
  retry,
}: {
  error: Error;
  retry: () => void;
}) {
  const missing = error instanceof PortalApiError && error.status === 404;
  return (
    <Card className="mx-auto max-w-2xl p-8 text-center sm:p-12">
      <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
        <ImageIcon className="size-5" />
      </span>
      <h2 className="display-type mt-5 text-2xl">
        {missing ? "Gallery not found" : "Gallery could not be loaded"}
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
        {missing
          ? "This gallery may have been removed or the link is no longer valid."
          : "Check your connection or access, then try again."}
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button asChild variant="outline">
          <Link href="/dashboard/galleries">
            <ArrowLeft className="size-4" /> Back to galleries
          </Link>
        </Button>
        {!missing ? (
          <Button onClick={retry}>
            <RefreshCw className="size-4" /> Try again
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

export function GalleryDetailClient({ galleryId }: { galleryId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const gallery = useQuery({
    queryKey: galleryDetailQueryKey(galleryId),
    queryFn: () =>
      api<DashboardGallery>(
        `/api/v1/galleries/${encodeURIComponent(galleryId)}`,
      ),
  });
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
    staleTime: 60_000,
  });
  const remove = useMutation({
    mutationFn: () =>
      api(`/api/v1/galleries/${encodeURIComponent(galleryId)}/permanent`, {
        method: "DELETE",
      }),
    onSuccess: async () => {
      toast.success(
        workspaces.galleries.delete?.successMessage ?? "Gallery deleted",
      );
      await queryClient.invalidateQueries({ queryKey: ["galleries"] });
      router.replace("/dashboard/galleries");
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Could not delete"),
  });

  if (gallery.isLoading) return <GalleryDetailsLoading />;
  if (gallery.error) {
    return (
      <GalleryLoadError
        error={gallery.error}
        retry={() => void gallery.refetch()}
      />
    );
  }
  if (!gallery.data) return null;

  const record = gallery.data;
  const imageCount = record.items.length;
  const canEdit = user.data?.permissions.includes("content.edit") ?? false;
  const canDelete = user.data?.permissions.includes("records.delete") ?? false;

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6">
      <nav aria-label="Breadcrumb">
        <Link
          href="/dashboard/galleries"
          className="inline-flex min-h-10 items-center gap-2 rounded-full px-3 text-xs font-bold text-muted transition hover:bg-ink/5 hover:text-ink"
        >
          <ArrowLeft className="size-4" /> Galleries
        </Link>
      </nav>

      <header className="overflow-hidden rounded-[1.7rem] bg-[#0b1a2e] text-paper shadow-[0_28px_70px_rgba(8,18,34,.18)]">
        {record.items[0] ? (
          <div className="relative h-[clamp(14rem,38vw,22rem)]">
            <Image
              fill
              unoptimized
              alt={
                record.items[0].caption ??
                record.items[0].media_name ??
                record.title
              }
              className="object-cover opacity-80"
              sizes="(max-width: 1280px) 100vw, 72rem"
              priority
              src={`/api/v1/media/${record.items[0].media_asset_id}/content`}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#0b1a2e] via-[#0b1a2e]/45 to-transparent" />
          </div>
        ) : null}
        <div className="relative flex flex-col justify-between gap-4 p-5 lg:flex-row lg:items-end sm:p-6">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="eyebrow text-gold">Gallery</p>
              <span
                className="inline-flex rounded-full bg-white/12 px-2.5 py-1 text-[.65rem] font-bold text-paper"
              >
                {humanize(record.status)}
              </span>
            </div>
            <h2 className="mt-2 max-w-3xl text-xl leading-snug font-semibold tracking-tight break-words sm:text-2xl">
              {record.title}
            </h2>
            <p className="mt-3 text-sm text-white/62">
              {imageCount} {imageCount === 1 ? "image" : "images"} · Last updated{" "}
              {formatDateTime(record.updated_at)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {record.status === "published" ? (
              <Button
                asChild
                size="sm"
                variant="ghost"
                className="text-white/75 hover:bg-white/10 hover:text-white"
              >
                <Link href={`/gallery/${record.slug}`} target="_blank">
                  <ExternalLink className="size-4" /> View public gallery
                </Link>
              </Button>
            ) : null}
            {canEdit ? (
              <Button asChild size="sm" className="bg-paper text-ink hover:bg-paper/90">
                <Link href={`/dashboard/galleries/${record.id}/edit`}>
                  <Pencil className="size-4" /> Edit gallery
                </Link>
              </Button>
            ) : null}
            {canDelete ? (
              <Button
                size="sm"
                variant="ghost"
                className="text-red-200 hover:bg-white/10"
                onClick={() => setConfirmDelete(true)}
              >
                <Trash2 className="size-4" /> Delete gallery
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="grid min-w-0 gap-5">
          <Card className="overflow-hidden">
            <div className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-5">
              <div>
                <p className="eyebrow text-gold">Album</p>
                <h3 className="mt-1.5 text-lg font-semibold tracking-tight">
                  Gallery images
                </h3>
              </div>
              <p className="text-xs leading-5 text-muted">
                Shown in public display order
              </p>
            </div>
            {imageCount ? (
              <div className="grid gap-4 px-4 pb-5 sm:grid-cols-2 sm:px-5">
                {record.items.map((item, index) => (
                  <figure
                    key={item.id}
                    className={cn(
                      "overflow-hidden rounded-[1.2rem] bg-ink/5",
                      index === 0 && imageCount > 1 && "sm:col-span-2",
                    )}
                  >
                    <div
                      className={cn(
                        "relative overflow-hidden bg-ink/5",
                        index === 0 && imageCount > 1
                          ? "aspect-[16/9]"
                          : "aspect-[4/3]",
                      )}
                    >
                      <Image
                        fill
                        unoptimized
                        alt={
                          item.caption ??
                          item.media_name ??
                          `${record.title}, image ${index + 1}`
                        }
                        className="object-cover"
                        sizes={
                          index === 0
                            ? "(max-width: 1280px) 100vw, 70vw"
                            : "(max-width: 640px) 100vw, 40vw"
                        }
                        priority={index === 0}
                        src={`/api/v1/media/${item.media_asset_id}/content`}
                      />
                      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-gradient-to-t from-black/70 via-black/15 to-transparent px-4 pt-12 pb-3 text-white">
                        <span className="text-[.65rem] font-black tracking-[.1em] uppercase">
                          Photo {String(index + 1).padStart(2, "0")}
                        </span>
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-black/35 px-2.5 py-1 text-[.6rem] font-bold backdrop-blur-sm">
                          {item.allow_download ? (
                            <Download className="size-3" />
                          ) : null}
                          {item.allow_download ? "Download on" : "View only"}
                        </span>
                      </div>
                    </div>
                    {item.caption ? (
                      <figcaption className="px-4 py-3 text-xs leading-5 text-muted">
                        {item.caption}
                      </figcaption>
                    ) : null}
                  </figure>
                ))}
              </div>
            ) : (
              <div className="grid min-h-72 place-items-center px-6 py-12 text-center">
                <div>
                  <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
                    <ImageIcon className="size-5" />
                  </span>
                  <p className="mt-4 font-bold">No images in this gallery</p>
                  <p className="mt-1 text-xs leading-5 text-muted">
                    Add photographs from the editor, or link an external album
                    for visitors.
                  </p>
                  {canEdit ? (
                    <Button asChild className="mt-5" size="sm">
                      <Link href={`/dashboard/galleries/${record.id}/edit`}>
                        <Pencil className="size-4" /> Add images
                      </Link>
                    </Button>
                  ) : null}
                </div>
              </div>
            )}
          </Card>

          {record.description ? (
            <Card className="p-5 sm:p-6">
              <p className="eyebrow text-coral">Introduction</p>
              <div className="mt-3 [&_.rich-text-content]:min-h-0 [&_.rich-text-content]:p-0 [&_.rich-text-content]:text-sm">
                <WorkspaceRichTextValue html={record.description} />
              </div>
            </Card>
          ) : null}
        </div>

        <aside className="grid gap-4 xl:sticky xl:top-[6rem]">
          <Card className="overflow-hidden">
            <div className="px-6 pt-6">
              <p className="eyebrow text-gold">Publishing</p>
            </div>
            <dl className="divide-y divide-line/70">
              <div className="px-6 py-4">
                <dt className="text-[.65rem] font-bold tracking-[.08em] text-muted uppercase">
                  Status
                </dt>
                <dd className="mt-2 text-sm font-bold">
                  {humanize(record.status)}
                </dd>
              </div>
              <div className="px-6 py-4">
                <dt className="text-[.65rem] font-bold tracking-[.1em] text-muted uppercase">
                  Public address
                </dt>
                <dd className="mt-2 min-w-0 break-all text-sm font-medium">
                  /gallery/{record.slug}
                </dd>
              </div>
              <div className="px-6 py-4">
                <dt className="flex items-center gap-1.5 text-[.65rem] font-bold tracking-[.1em] text-muted uppercase">
                  <CalendarClock className="size-3.5" /> Published
                </dt>
                <dd className="mt-2 text-sm font-medium">
                  {formatDateTime(record.published_at)}
                </dd>
              </div>
              <div className="px-6 py-4">
                <dt className="text-[.65rem] font-bold tracking-[.1em] text-muted uppercase">
                  Created
                </dt>
                <dd className="mt-2 text-sm font-medium">
                  {formatDateTime(record.created_at)}
                </dd>
              </div>
            </dl>
          </Card>

          {record.external_album_url ? (
            <Card className="p-5">
              <span className="grid size-10 place-items-center rounded-xl bg-sky/10 text-sky">
                <Link2 className="size-4" />
              </span>
              <p className="mt-4 text-sm font-black">External album</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Visitors can also open the linked album.
              </p>
              <a
                href={record.external_album_url}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-flex min-h-10 max-w-full items-center gap-2 rounded-full border border-line px-4 text-xs font-bold text-ink transition hover:border-ink/30"
              >
                <ExternalLink className="size-3.5 shrink-0" />
                <span className="truncate">Open external album</span>
              </a>
            </Card>
          ) : null}
        </aside>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this gallery?"
        description={
          workspaces.galleries.delete?.confirm ??
          "Permanently delete this gallery? This cannot be undone. Its shared media assets will be retained."
        }
        confirmLabel="Delete gallery"
        danger
        busy={remove.isPending}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
