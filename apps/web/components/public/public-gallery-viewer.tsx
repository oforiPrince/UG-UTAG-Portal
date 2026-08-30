"use client";

import { ChevronLeft, ChevronRight, Download, Expand, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { publicMediaUrl } from "@/lib/public-media";

export type PublicGalleryImage = {
  id: string;
  url: string;
  alt_text: string | null;
  caption: string | null;
  credit: string | null;
  allow_download: boolean;
  download_url: string | null;
  original_filename: string | null;
};

type PublicGalleryViewerProps = {
  galleryTitle: string;
  images: PublicGalleryImage[];
};

function imageAlt(image: PublicGalleryImage, galleryTitle: string) {
  return image.alt_text ?? image.caption ?? galleryTitle;
}

function nearbyIndices(total: number, current: number) {
  const visible = Math.min(total, 7);
  const start = Math.max(
    0,
    Math.min(current - Math.floor(visible / 2), total - visible),
  );
  return Array.from({ length: visible }, (_, offset) => start + offset);
}

function GalleryLightbox({
  activeIndex,
  galleryTitle,
  images,
  onChange,
  onDismiss,
}: PublicGalleryViewerProps & {
  activeIndex: number;
  onChange: (index: number) => void;
  onDismiss: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const touchStartRef = useRef<{ x: number; y: number } | null>(null);
  const titleId = useId();
  const statusId = useId();
  const current = images[activeIndex];
  const total = images.length;
  const goPrevious = () => onChange((activeIndex - 1 + total) % total);
  const goNext = () => onChange((activeIndex + 1) % total);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.showModal();
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (dialog.open) dialog.close();
    };
  }, []);

  useEffect(() => {
    const preload = [
      images[(activeIndex - 1 + total) % total],
      images[(activeIndex + 1) % total],
    ];
    preload.forEach((image) => {
      const nextImage = new window.Image();
      nextImage.src = publicMediaUrl(image.id, "w1600") ?? image.url;
    });
  }, [activeIndex, images, total]);

  return (
    <dialog
      ref={dialogRef}
      aria-describedby={statusId}
      aria-labelledby={titleId}
      className="m-0 h-dvh max-h-none w-screen max-w-none overflow-hidden bg-transparent p-0 text-white backdrop:bg-[#06111f]/96 backdrop:backdrop-blur-sm"
      onClose={onDismiss}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          goPrevious();
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          goNext();
        } else if (event.key === "Home") {
          event.preventDefault();
          onChange(0);
        } else if (event.key === "End") {
          event.preventDefault();
          onChange(total - 1);
        } else if (event.key === "Escape") {
          event.preventDefault();
          dialogRef.current?.close();
        }
      }}
    >
      <div className="relative h-dvh overflow-hidden bg-[radial-gradient(circle_at_50%_35%,#142c47_0%,#081522_48%,#050c13_100%)]">
        <header className="absolute inset-x-0 top-0 z-20 flex min-h-20 items-start gap-3 bg-gradient-to-b from-[#06111f]/96 via-[#06111f]/84 to-transparent px-3 pt-3 pb-8 sm:min-h-24 sm:items-center sm:px-5 sm:pt-3 sm:pb-10">
          <div className="min-w-0 flex-1">
            <p
              id={titleId}
              className="truncate text-sm font-bold text-white sm:text-base"
            >
              {galleryTitle}
            </p>
            <p
              id={statusId}
              aria-live="polite"
              className="mt-0.5 text-[.68rem] font-extrabold tracking-[.12em] text-gold uppercase"
            >
              Image {activeIndex + 1} of {total}
            </p>
          </div>

          <p className="hidden text-xs text-white/52 lg:block">
            Use arrow keys to browse
          </p>
          {current.allow_download && current.download_url ? (
            <a
              aria-label={`Download image ${activeIndex + 1}`}
              className="inline-flex min-h-11 items-center gap-2 rounded-full border border-white/16 bg-white/8 px-3 text-xs font-bold text-white transition hover:border-gold/60 hover:bg-white/14 focus-visible:outline-gold sm:px-4"
              download={current.original_filename ?? undefined}
              href={current.download_url}
            >
              <Download aria-hidden="true" className="size-4" />
              <span className="hidden sm:inline">Download</span>
            </a>
          ) : null}
          <button
            ref={closeButtonRef}
            aria-label="Close image viewer"
            className="grid size-11 shrink-0 place-items-center rounded-full border border-white/16 bg-white/8 text-white transition hover:border-white/34 hover:bg-white/14 focus-visible:outline-gold"
            onClick={() => dialogRef.current?.close()}
            type="button"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        </header>

        <main
          className="absolute inset-0 flex min-h-0 items-center justify-center overflow-hidden px-3 py-20 sm:px-20 sm:py-24 lg:px-24"
          onClick={(event) => {
            if (event.target === event.currentTarget)
              dialogRef.current?.close();
          }}
          onTouchEnd={(event) => {
            const start = touchStartRef.current;
            touchStartRef.current = null;
            if (!start) return;
            const touch = event.changedTouches[0];
            const deltaX = touch.clientX - start.x;
            const deltaY = touch.clientY - start.y;
            if (Math.abs(deltaX) < 55 || Math.abs(deltaX) < Math.abs(deltaY)) {
              return;
            }
            if (deltaX > 0) goPrevious();
            else goNext();
          }}
          onTouchStart={(event) => {
            const touch = event.touches[0];
            touchStartRef.current = { x: touch.clientX, y: touch.clientY };
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            key={current.id}
            alt={imageAlt(current, galleryTitle)}
            className="max-h-full max-w-full select-none object-contain shadow-[0_24px_80px_rgb(0_0_0_/_48%)] motion-safe:animate-[gallery-image-in_220ms_ease-out]"
            decoding="async"
            draggable={false}
            src={publicMediaUrl(current.id, "w1600") ?? current.url}
          />

          {total > 1 ? (
            <>
              <button
                aria-label="View previous image"
                className="absolute left-3 hidden size-13 place-items-center rounded-full border border-white/16 bg-[#07131f]/66 text-white shadow-xl backdrop-blur-md transition hover:scale-105 hover:border-gold/60 hover:bg-[#10263c] focus-visible:outline-gold sm:grid lg:left-6"
                onClick={goPrevious}
                type="button"
              >
                <ChevronLeft aria-hidden="true" className="size-6" />
              </button>
              <button
                aria-label="View next image"
                className="absolute right-3 hidden size-13 place-items-center rounded-full border border-white/16 bg-[#07131f]/66 text-white shadow-xl backdrop-blur-md transition hover:scale-105 hover:border-gold/60 hover:bg-[#10263c] focus-visible:outline-gold sm:grid lg:right-6"
                onClick={goNext}
                type="button"
              >
                <ChevronRight aria-hidden="true" className="size-6" />
              </button>
            </>
          ) : null}
        </main>

        <footer className="absolute inset-x-0 bottom-0 z-20 bg-gradient-to-t from-[#06111f]/96 via-[#06111f]/86 to-transparent px-3 pt-8 pb-3 sm:px-5 sm:pt-10 sm:pb-4">
          <div className="mx-auto flex max-w-6xl items-center gap-3">
            {total > 1 ? (
              <button
                aria-label="View previous image"
                className="grid size-11 shrink-0 place-items-center rounded-full border border-white/16 bg-white/8 text-white sm:hidden"
                onClick={goPrevious}
                type="button"
              >
                <ChevronLeft aria-hidden="true" className="size-5" />
              </button>
            ) : null}

            <div className="min-w-0 flex-1 sm:grid sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-6">
              <div className="min-w-0">
                {current.caption ? (
                  <p className="line-clamp-2 text-xs leading-5 text-white/84 sm:text-sm">
                    {current.caption}
                  </p>
                ) : (
                  <p className="text-xs text-white/46">{galleryTitle}</p>
                )}
                {current.credit ? (
                  <p className="mt-1 text-[.68rem] font-semibold text-white/50">
                    Credit: {current.credit}
                  </p>
                ) : null}
              </div>

              {total > 1 ? (
                <div
                  aria-label="Nearby images"
                  className="mt-3 hidden items-center gap-1.5 sm:flex"
                  role="group"
                >
                  {nearbyIndices(total, activeIndex).map((index) => {
                    const image = images[index];
                    const selected = index === activeIndex;
                    return (
                      <button
                        key={image.id}
                        aria-label={`View image ${index + 1}`}
                        aria-pressed={selected}
                        className={`relative h-11 w-14 overflow-hidden rounded border transition focus-visible:outline-gold ${
                          selected
                            ? "border-gold ring-1 ring-gold"
                            : "border-white/14 opacity-52 hover:border-white/44 hover:opacity-100"
                        }`}
                        onClick={() => onChange(index)}
                        type="button"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          alt=""
                          aria-hidden="true"
                          className="h-full w-full object-cover"
                          src={publicMediaUrl(image.id, "w480") ?? image.url}
                        />
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>

            {total > 1 ? (
              <button
                aria-label="View next image"
                className="grid size-11 shrink-0 place-items-center rounded-full border border-white/16 bg-white/8 text-white sm:hidden"
                onClick={goNext}
                type="button"
              >
                <ChevronRight aria-hidden="true" className="size-5" />
              </button>
            ) : null}
          </div>
        </footer>
      </div>
    </dialog>
  );
}

export function PublicGalleryViewer({
  galleryTitle,
  images,
}: PublicGalleryViewerProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  function openViewer(index: number) {
    openerRef.current = document.activeElement as HTMLElement | null;
    setActiveIndex(index);
  }

  function dismissViewer() {
    setActiveIndex(null);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  }

  return (
    <>
      <div className="columns-1 gap-5 sm:columns-2 lg:columns-3">
        {images.map((image, index) => (
          <figure
            key={image.id}
            className="mb-5 break-inside-avoid overflow-hidden rounded-md border border-line bg-white shadow-sm"
          >
            <button
              aria-label={`Open image ${index + 1} of ${images.length}`}
              className="group relative block w-full cursor-zoom-in overflow-hidden bg-[#edf2f7] text-left focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
              onClick={() => openViewer(index)}
              type="button"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt={imageAlt(image, galleryTitle)}
                className="h-auto w-full transition duration-300 motion-safe:group-hover:scale-[1.018]"
                decoding="async"
                loading="lazy"
                sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                src={publicMediaUrl(image.id, "w960") ?? image.url}
                srcSet={`${publicMediaUrl(image.id, "w480") ?? image.url} 480w, ${publicMediaUrl(image.id, "w960") ?? image.url} 960w, ${publicMediaUrl(image.id, "w1600") ?? image.url} 1600w`}
              />
              <span className="pointer-events-none absolute right-3 bottom-3 inline-flex items-center gap-2 rounded-full border border-white/30 bg-[#07182c]/76 px-3 py-2 text-[.68rem] font-extrabold tracking-[.08em] text-white uppercase opacity-0 shadow-lg backdrop-blur-md transition group-hover:opacity-100 group-focus-visible:opacity-100">
                <Expand aria-hidden="true" className="size-3.5" /> View
              </span>
            </button>

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
                    className="inline-flex min-h-9 w-fit items-center gap-2 font-bold text-sky transition hover:text-coral"
                    download={image.original_filename ?? undefined}
                    href={image.download_url}
                  >
                    <Download aria-hidden="true" className="size-3.5" />
                    Download
                  </a>
                ) : null}
              </figcaption>
            ) : null}
          </figure>
        ))}
      </div>

      {activeIndex !== null ? (
        <GalleryLightbox
          activeIndex={activeIndex}
          galleryTitle={galleryTitle}
          images={images}
          onChange={setActiveIndex}
          onDismiss={dismissViewer}
        />
      ) : null}
    </>
  );
}
