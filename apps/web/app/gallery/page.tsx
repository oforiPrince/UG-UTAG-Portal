import { ArrowRight, Images } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageHero } from "@/components/public/page-hero";
import { MediaCover } from "@/components/public/media-cover";
import { PublicEmptyState } from "@/components/public/public-empty-state";
import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";

export const metadata: Metadata = { title: "Gallery" };
type GalleryImage = {
  id: string;
  url: string;
  alt_text: string | null;
  caption: string | null;
};
type Gallery = {
  id: string;
  slug: string;
  title: string;
  description: string;
  image_count: number;
  external_album_url: string | null;
  images: GalleryImage[];
};

export default async function GalleryPage() {
  const galleries = await publicApi<Gallery[]>("/api/v1/public/galleries", [], {
    revalidate: false,
  });
  return (
    <PublicShell>
      <PageHero
        eyebrow="Gallery"
        title="UG UTAG in pictures"
        intro="A moderated visual record of meetings, leadership engagement, scholarly exchange, and association life."
      />
      <section className="mx-auto grid max-w-[82rem] gap-6 px-5 py-16 sm:px-6 md:grid-cols-2 lg:px-8 lg:py-22">
        {galleries.length === 0 && (
          <PublicEmptyState
            title="No public galleries yet"
            description="Approved photographs from UG UTAG activities will appear here with captions and credits."
          />
        )}
        {galleries.map((gallery) => (
          <Link
            href={`/gallery/${gallery.slug}`}
            key={gallery.id}
            className="group overflow-hidden rounded-md border border-line bg-white shadow-[0_8px_26px_rgb(23_43_69_/_8%)]"
          >
            {gallery.images[0] ? (
              <MediaCover
                assetId={gallery.images[0].id}
                alt={gallery.images[0].alt_text ?? gallery.title}
                className="aspect-[16/9] transition duration-500 group-hover:scale-[1.015]"
                variant="w960"
              >
                <div className="absolute inset-0 bg-gradient-to-t from-[#0e2b49]/55 to-transparent" />
              </MediaCover>
            ) : (
              <div className="grid aspect-[16/9] place-items-center bg-[#edf3f8]">
                <Images className="size-10 text-[#8fa2b6]" />
              </div>
            )}
            <div className="p-6">
              <div className="flex items-center justify-between gap-5">
                <h2 className="text-xl font-extrabold text-[#172f4d] group-hover:text-coral">
                  {gallery.title}
                </h2>
                <span className="inline-flex shrink-0 items-center gap-2 rounded-full bg-[#edf3f8] px-3 py-1.5 text-[.68rem] font-extrabold text-coral">
                  <Images className="size-3.5" />
                  {gallery.image_count}
                </span>
              </div>
              {gallery.description ? (
                <div
                  className="mt-3 line-clamp-3 text-sm leading-6 text-muted"
                  dangerouslySetInnerHTML={{ __html: gallery.description }}
                />
              ) : null}
              {gallery.external_album_url && gallery.image_count === 0 ? (
                <p className="mt-3 text-xs font-semibold text-muted">
                  Linked external album
                </p>
              ) : null}
              <span className="mt-5 inline-flex items-center gap-2 text-xs font-extrabold text-coral">
                View gallery{" "}
                <ArrowRight className="size-4 transition group-hover:translate-x-1" />
              </span>
            </div>
          </Link>
        ))}
      </section>
    </PublicShell>
  );
}
