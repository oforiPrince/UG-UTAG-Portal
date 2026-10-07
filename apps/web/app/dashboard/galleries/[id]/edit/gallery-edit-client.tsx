"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ImageIcon, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { MutationForm } from "@/components/dashboard/workspace-client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PortalApiError, api } from "@/lib/api";
import { galleryDetailQueryKey, type DashboardGallery } from "@/lib/galleries";
import { workspacePresentations } from "@/lib/workspace-presentation";
import { workspaces } from "@/lib/workspaces";

type User = { permissions: string[] };

export function GalleryEditClient({ galleryId }: { galleryId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const detailHref = `/dashboard/galleries/${galleryId}`;
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

  if (gallery.isLoading || user.isLoading) {
    return (
      <div
        className="grid animate-pulse gap-5"
        aria-label="Loading gallery editor"
      >
        <div className="h-10 w-44 rounded-full bg-ink/5" />
        <div className="h-[42rem] rounded-[1.35rem] bg-ink/5" />
      </div>
    );
  }

  if (gallery.error || !gallery.data) {
    const missing =
      gallery.error instanceof PortalApiError && gallery.error.status === 404;
    return (
      <Card className="mx-auto max-w-2xl p-8 text-center sm:p-12">
        <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
          <ImageIcon className="size-5" />
        </span>
        <h2 className="display-type mt-5 text-2xl">
          {missing ? "Gallery not found" : "Editor could not be loaded"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          {missing
            ? "This gallery may have been removed."
            : "Check your connection or access, then try again."}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button asChild variant="outline">
            <Link href="/dashboard/galleries">
              <ArrowLeft className="size-4" /> Back to galleries
            </Link>
          </Button>
          {!missing ? (
            <Button onClick={() => void gallery.refetch()}>
              <RefreshCw className="size-4" /> Try again
            </Button>
          ) : null}
        </div>
      </Card>
    );
  }

  const permissions = user.data?.permissions ?? [];
  if (!permissions.includes("content.edit")) {
    return (
      <Card className="mx-auto max-w-2xl p-8 text-center sm:p-12">
        <h2 className="display-type text-2xl">Editing is not available</h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          You can view this gallery, but your account cannot change it.
        </p>
        <Button asChild className="mt-6" variant="outline">
          <Link href={detailHref}>
            <ArrowLeft className="size-4" /> Back to gallery
          </Link>
        </Button>
      </Card>
    );
  }

  const mutation = workspaces.galleries.update;
  if (!mutation) return null;

  return (
    <div className="grid gap-5">
      <MutationForm
        config={workspaces.galleries}
        mutation={mutation}
        mode="edit"
        row={gallery.data}
        permissions={permissions}
        steps={workspacePresentations.galleries.editSteps}
        variant="page"
        draftKey={`workspace-draft:galleries:edit:${galleryId}`}
        recoverableFields={workspacePresentations.galleries.recoverableFields}
        showCloseButton={false}
        cancelLabel="Cancel"
        onSaved={(saved) => {
          queryClient.setQueryData(galleryDetailQueryKey(galleryId), saved);
          router.push(detailHref);
        }}
        close={() => router.push(detailHref)}
      />
    </div>
  );
}
