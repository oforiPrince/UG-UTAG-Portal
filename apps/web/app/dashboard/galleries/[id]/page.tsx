import { GalleryDetailClient } from "./gallery-detail-client";

export default async function DashboardGalleryDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <GalleryDetailClient galleryId={id} />;
}
