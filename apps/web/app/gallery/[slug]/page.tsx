import { ArrowLeft, Camera, Download, ExternalLink } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Button } from "@/components/ui/button";
import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";

type GalleryImage = {
  id: string;
  url: string;
  alt_text: string | null;
  caption: string | null;
  credit: string | null;
  allow_download: boolean;
  download_url: string | null;
  original_filename: string | null;
};
type Gallery = {
  slug: string;
  title: string;
  description: string;
  external_album_url: string | null;
  images: GalleryImage[];
};

export default async function GalleryDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const gallery = await publicApi<Gallery | null>(
    `/api/v1/public/galleries/${encodeURIComponent(slug)}`,
    null,
    { revalidate: false },
  );
  if (!gallery) notFound();

  return (
    <PublicShell>
      <header className="bg-[#122b48] text-white">
        <div className="mx-auto max-w-[82rem] px-5 py-14 sm:px-6 lg:px-8 lg:py-18">
          <Link
            href="/gallery"
            className="inline-flex items-center gap-2 text-xs font-bold text-white/72 hover:text-white"
          >
            <ArrowLeft className="size-4" /> Back to galleries
          </Link>
          <p className="mt-8 text-[.7rem] font-extrabold tracking-[.14em] text-gold uppercase">
            Public gallery
          </p>
          <h1 className="display-type mt-4 text-4xl text-white sm:text-5xl">
            {gallery.title}
          </h1>
          {gallery.description ? (
            <div
              className="mt-4 max-w-3xl text-sm leading-7 text-white/70 sm:text-base [&_a]:font-bold [&_a]:text-gold [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-gold [&_blockquote]:pl-4 [&_h2]:font-bold [&_h2]:text-white [&_h3]:font-bold [&_h3]:text-white [&_li]:ml-5 [&_li]:list-disc [&_p+p]:mt-3"
              dangerouslySetInnerHTML={{ __html: gallery.description }}
            />
          ) : null}
          {gallery.external_album_url ? (
            <Button className="mt-8 rounded-md" asChild>
              <a
                href={gallery.external_album_url}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink className="size-4" /> Open full album
              </a>
            </Button>
          ) : null}
        </div>
        <div className="h-1 bg-gold" />
      </header>
      <section className="mx-auto max-w-[82rem] px-5 py-14 sm:px-6 lg:px-8 lg:py-18">
        {gallery.images.length === 0 ? (
          <div className="grid min-h-64 place-items-center rounded-md border border-dashed border-line bg-panel text-center">
            <div>
              <Camera className="mx-auto size-8 text-coral" />
              <p className="mt-3 text-sm font-bold">
                {gallery.external_album_url
                  ? "This gallery links to an external album."
                  : "No approved public images in this gallery."}
              </p>
              {gallery.external_album_url ? (
                <Button className="mt-5 rounded-md" asChild>
                  <a
                    href={gallery.external_album_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink className="size-4" /> Open album
                  </a>
                </Button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="columns-1 gap-5 sm:columns-2 lg:columns-3">
            {gallery.images.map((image) => (
              <figure
                key={image.id}
                className="mb-5 break-inside-avoid overflow-hidden rounded-md border border-line bg-white shadow-sm"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image.url}
                  alt={image.alt_text ?? image.caption ?? gallery.title}
                  className="h-auto w-full"
                  loading="lazy"
                />
                {image.caption || image.credit || image.allow_download ? (
                  <figcaption className="grid gap-3 border-t border-line px-4 py-3 text-xs leading-5 text-muted">
                    {image.caption || image.credit ? (
                      <div>
                        {image.caption}
                        {image.credit ? (
                          <span className="block font-semibold">
                            Credit: {image.credit}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                    {image.allow_download && image.download_url ? (
                      <a
                        href={image.download_url}
                        download={image.original_filename ?? undefined}
                        className="inline-flex w-fit items-center gap-2 font-bold text-sky transition hover:text-coral"
                      >
                        <Download className="size-3.5" />
                        Download
                      </a>
                    ) : null}
                  </figcaption>
                ) : null}
              </figure>
            ))}
          </div>
        )}
      </section>
    </PublicShell>
  );
}
