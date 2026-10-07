"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { publicMediaUrl } from "@/lib/public-media";

export type HomeCarouselSlide = {
  id: string;
  title: string;
  description: string;
  media_asset_id: string;
  link_url: string | null;
  order: number;
  is_published: boolean;
};

export function HomeHero({
  eyebrow,
  headline,
  introduction,
  slides,
}: {
  eyebrow?: string;
  headline?: string;
  introduction?: string;
  slides: HomeCarouselSlide[];
}) {
  const [active, setActive] = useState(0);
  const slide = slides[active];
  const background =
    publicMediaUrl(slide?.media_asset_id, "w1600") ?? "/brand/hero-meeting.jpg";
  const title =
    slide?.title || headline || "Advancing academic excellence. Protecting member welfare.";
  const copy =
    introduction ||
    "The collective voice of teaching and research staff of the University of Ghana.";

  function move(direction: number) {
    setActive((current) => (current + direction + slides.length) % slides.length);
  }

  return (
    <section
      className="relative isolate overflow-hidden bg-[#061421] text-white"
      aria-roledescription={slides.length > 1 ? "carousel" : undefined}
      aria-label="UG UTAG highlights"
    >
      <div className="absolute inset-0 -z-20 overflow-hidden lg:hidden" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={`${background}-ambient`}
          src={background}
          alt=""
          className="size-full scale-110 object-cover opacity-55 blur-[24px] saturate-75"
          loading="eager"
          decoding="async"
        />
      </div>
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,rgba(4,16,28,.08)_0%,rgba(4,16,28,.2)_55%,rgba(4,16,28,.72)_100%)]" />

      <div className="relative h-72 w-full sm:h-96 lg:h-[clamp(34rem,48vw,44rem)]">
        {/* Prefer a real img for LCP: browsers can prioritize/decode without waiting on CSS. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={background}
          src={background}
          alt=""
          aria-hidden="true"
          className="absolute inset-0 size-full object-contain object-center transition-opacity duration-500 lg:object-cover lg:object-[center_45%]"
          fetchPriority="high"
          loading="eager"
          decoding="async"
          sizes="100vw"
        />
      </div>

      <div className="relative z-10 bg-[#071a2d] py-9 lg:absolute lg:inset-x-0 lg:bottom-0 lg:bg-transparent lg:bg-gradient-to-t lg:from-[#061421] lg:via-[#071a2d]/92 lg:to-transparent lg:pt-32 lg:pb-9">
        <div className="mx-auto flex w-full max-w-[82rem] flex-col items-center px-5 text-center sm:px-6 lg:px-8">
          <div className="max-w-5xl" aria-live="polite">
            <p className="inline-flex items-center gap-3 text-[.7rem] font-extrabold tracking-[.18em] text-gold uppercase">
              <span className="h-px w-8 bg-gold" /> {eyebrow || "University of Ghana Branch"}
              <span className="h-px w-8 bg-gold" />
            </p>
            <h1 className="display-type mt-4 text-[clamp(2.15rem,3.4vw,3.35rem)] leading-[1.04] text-white">
              {title}
            </h1>

            {slide?.description ? (
              <div
                className="mx-auto mt-4 max-w-3xl text-base leading-7 text-white/75 sm:text-lg sm:leading-8 [&_a]:font-bold [&_a]:text-gold [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-gold [&_blockquote]:pl-4 [&_h2]:font-bold [&_h2]:text-white [&_h3]:font-bold [&_h3]:text-white [&_li]:ml-5 [&_li]:list-disc [&_p+p]:mt-3"
                dangerouslySetInnerHTML={{ __html: slide.description }}
              />
            ) : (
              <p className="mx-auto mt-4 max-w-3xl text-base leading-7 text-white/75 sm:text-lg sm:leading-8">
                {copy}
              </p>
            )}
          </div>

          {slides.length > 1 ? (
            <div className="mt-7 flex items-center gap-3">
              <Button
                size="icon"
                variant="outline"
                className="size-11 rounded-full border-white/35 bg-black/15 text-white backdrop-blur-sm hover:bg-white hover:text-[#112b48]"
                onClick={() => move(-1)}
                aria-label="Previous homepage slide"
              >
                <ChevronLeft className="size-4" />
              </Button>
              <span className="min-w-20 text-center text-[.7rem] font-bold tracking-[.14em] text-white/70">
                {String(active + 1).padStart(2, "0")} / {String(slides.length).padStart(2, "0")}
              </span>
              <Button
                size="icon"
                variant="outline"
                className="size-11 rounded-full border-white/35 bg-black/15 text-white backdrop-blur-sm hover:bg-white hover:text-[#112b48]"
                onClick={() => move(1)}
                aria-label="Next homepage slide"
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          ) : null}
        </div>
      </div>
      <div className="absolute inset-x-0 bottom-0 h-1 bg-gold" />
    </section>
  );
}
