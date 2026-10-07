import type { WorkspaceRow } from "@/lib/workspaces";

export type DashboardGalleryItem = {
  id: string;
  media_asset_id: string;
  media_name: string | null;
  position: number;
  caption: string | null;
  allow_download: boolean;
};

export type DashboardGallery = WorkspaceRow & {
  id: string;
  slug: string;
  title: string;
  description: string;
  external_album_url: string | null;
  status: "draft" | "review" | "published" | "archived";
  published_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  items: DashboardGalleryItem[];
};

export function galleryDetailQueryKey(galleryId: string) {
  return ["galleries", "detail", galleryId] as const;
}
