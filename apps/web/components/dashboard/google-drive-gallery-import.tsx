"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HardDrive, LoaderCircle, Unplug } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { API_URL, api, PortalApiError } from "@/lib/api";

type DriveStatus = {
  configured: boolean;
  connected: boolean;
  email: string | null;
};

type ImportJob = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  result_json: {
    imported?: number;
    reused?: number;
    failed?: number;
    attached?: number;
    media_asset_ids?: string[];
    oversized?: number;
    skipped_capacity?: number;
    gallery_version?: number;
  };
  error_message: string | null;
};

async function waitForJob(
  jobId: string,
  onProgress: (progress: number) => void,
) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const job = await api<ImportJob>(`/api/v1/jobs/${jobId}`);
    onProgress(Math.max(0, Math.min(job.progress, 100)));
    if (job.status === "completed") return job;
    if (job.status === "failed") {
      throw new Error(job.error_message || "Google Drive import failed");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
  }
  throw new Error(
    "Google Drive import is still running. Refresh the gallery soon.",
  );
}

export function GoogleDriveGalleryImport({
  galleryId,
  folderUrlHint,
  onImported,
}: {
  galleryId?: string;
  folderUrlHint?: string;
  onImported?: (
    mediaIds: string[],
    folderUrl: string,
    galleryVersion?: number,
  ) => void;
}) {
  const queryClient = useQueryClient();
  const [folderUrl, setFolderUrl] = useState(folderUrlHint ?? "");
  const [importProgress, setImportProgress] = useState<number | null>(null);
  const status = useQuery({
    queryKey: ["integrations", "google-drive", "status"],
    queryFn: () => api<DriveStatus>("/api/v1/integrations/google-drive/status"),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const drive = params.get("drive");
    if (!drive) return;
    if (drive === "connected") {
      toast.success("Google Drive connected");
      void queryClient.invalidateQueries({
        queryKey: ["integrations", "google-drive", "status"],
      });
    } else if (drive === "error") {
      toast.error("Google Drive connection failed. Try again.");
    }
    params.delete("drive");
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
    window.history.replaceState({}, "", next);
  }, [queryClient]);

  const disconnect = useMutation({
    mutationFn: () =>
      api<{ message: string }>("/api/v1/integrations/google-drive", {
        method: "DELETE",
      }),
    onSuccess: async (data) => {
      toast.success(data.message);
      await queryClient.invalidateQueries({
        queryKey: ["integrations", "google-drive", "status"],
      });
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Disconnect failed"),
  });

  const importFolder = useMutation({
    mutationFn: async () => {
      if (!galleryId) {
        throw new Error("Save the gallery before importing from Google Drive");
      }
      const started = await api<{ job_id: string }>(
        `/api/v1/galleries/${galleryId}/import/google-drive`,
        {
          method: "POST",
          body: { folder_url: folderUrl.trim() },
        },
      );
      setImportProgress(0);
      return waitForJob(started.job_id, setImportProgress);
    },
    onSuccess: async (job) => {
      const ids = (job.result_json.media_asset_ids ?? []).map(String);
      const attached = job.result_json.attached ?? ids.length;
      const failed = job.result_json.failed ?? 0;
      const oversized = job.result_json.oversized ?? 0;
      const skippedCapacity = job.result_json.skipped_capacity ?? 0;
      toast.success(
        `Imported ${attached} image${attached === 1 ? "" : "s"} from Google Drive` +
          (failed || oversized || skippedCapacity
            ? ` (${failed} failed, ${oversized} too large, ${skippedCapacity} over gallery limit)`
            : ""),
      );
      onImported?.(ids, folderUrl.trim(), job.result_json.gallery_version);
      await queryClient.invalidateQueries({ queryKey: ["galleries"] });
      await queryClient.invalidateQueries({
        queryKey: ["ready-public-images"],
      });
    },
    onError: (error) => {
      const message =
        error instanceof PortalApiError || error instanceof Error
          ? error.message
          : "Import failed";
      toast.error(message);
    },
    onSettled: () => setImportProgress(null),
  });

  if (status.isLoading) {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-xl border border-dashed border-line bg-panel/60 px-4 py-3 text-xs text-muted">
        <LoaderCircle className="size-4 animate-spin" /> Checking Google Drive…
      </div>
    );
  }

  if (status.isError) {
    return (
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed border-line bg-panel/60 px-4 py-3 text-xs text-muted">
        <span>Google Drive status could not be loaded.</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void status.refetch()}
        >
          Try again
        </Button>
      </div>
    );
  }

  if (!status.data?.configured) {
    return (
      <div className="mt-3 rounded-xl border border-dashed border-line bg-panel/60 px-4 py-3 text-xs leading-5 text-muted">
        Google Drive import is not configured on this server. Ask an
        administrator to set the Google OAuth client credentials.
      </div>
    );
  }

  return (
    <div className="mt-3 grid gap-3 rounded-xl border border-line bg-panel/80 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold">Import from Google Drive</p>
          <p className="mt-1 text-[.7rem] font-normal leading-5 text-muted">
            Copies images into the Media library and adds them to this gallery.
            The external album link below stays as an optional visitor shortcut.
          </p>
        </div>
        {status.data.connected ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[.7rem] font-normal text-muted">
              Connected as {status.data.email || "Google account"}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disconnect.isPending}
              onClick={() => disconnect.mutate()}
            >
              {disconnect.isPending ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <Unplug className="size-3.5" />
              )}
              Disconnect
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              window.location.href = `${API_URL}/api/v1/integrations/google-drive/connect`;
            }}
          >
            <HardDrive className="size-3.5" />
            Connect Google Drive
          </Button>
        )}
      </div>
      {status.data.connected && galleryId ? (
        <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
          <label className="grid gap-1.5 text-[.7rem] font-bold">
            Drive folder link
            <input
              type="url"
              required
              value={folderUrl}
              placeholder="https://drive.google.com/drive/folders/…"
              onChange={(event) => setFolderUrl(event.target.value)}
              className="min-h-11 rounded-xl border border-line bg-paper px-3 text-sm font-normal outline-none focus:border-ink/25"
            />
          </label>
          <Button
            type="button"
            disabled={importFolder.isPending || folderUrl.trim().length < 10}
            onClick={() => importFolder.mutate()}
          >
            {importFolder.isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <HardDrive className="size-4" />
            )}
            {importFolder.isPending ? "Importing…" : "Import images"}
          </Button>
          {importFolder.isPending && importProgress !== null ? (
            <div
              className="grid gap-1 sm:col-span-2"
              role="status"
              aria-live="polite"
            >
              <div className="h-1.5 overflow-hidden rounded-full bg-line">
                <div
                  className="h-full rounded-full bg-sky transition-[width]"
                  style={{ width: `${importProgress}%` }}
                />
              </div>
              <span className="text-[.68rem] font-normal text-muted">
                Importing and checking images… {importProgress}%
              </span>
            </div>
          ) : null}
        </div>
      ) : status.data.connected ? (
        <p className="text-[.7rem] font-normal leading-5 text-muted">
          Save this gallery first, then reopen edit to import a Drive folder.
        </p>
      ) : null}
    </div>
  );
}
