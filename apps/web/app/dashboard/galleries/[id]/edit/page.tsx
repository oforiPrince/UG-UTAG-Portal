import { GalleryEditClient } from "./gallery-edit-client";

export default async function DashboardGalleryEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <GalleryEditClient galleryId={id} />;
}
