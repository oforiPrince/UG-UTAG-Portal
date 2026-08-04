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
      className="relative isolate flex min-h-[30rem] items-center overflow-hidden bg-[#112b48] text-white sm:min-h-[32rem]"
      aria-roledescription={slides.length > 1 ? "carousel" : undefined}
      aria-label="UG UTAG highlights"
    >
      {/* Prefer a real img for LCP: browsers can prioritize/decode without waiting on CSS. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        key={background}
        src={background}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 -z-20 size-full object-cover object-[56%_center] transition-opacity duration-500 lg:object-center"
        fetchPriority="high"
        loading="eager"
        decoding="async"
        sizes="100vw"
      />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(10,34,59,.95)_0%,rgba(10,34,59,.82)_45%,rgba(10,34,59,.3)_100%)]" />
      <div className="mx-auto w-full max-w-[82rem] px-5 py-16 sm:px-6 lg:px-8">
        <div className="max-w-2xl" aria-live="polite">
          <p className="inline-flex items-center gap-3 text-[.72rem] font-extrabold tracking-[.16em] text-gold uppercase">
            <span className="h-px w-8 bg-gold" /> {eyebrow || "University of Ghana Branch"}
          </p>
          <h1 className="display-type mt-5 text-[clamp(2.25rem,4vw,3.75rem)] leading-[1.06] text-white">
            {title}
          </h1>
          {slide?.description ? (
            <div
              className="mt-6 max-w-2xl text-base leading-8 text-white/80 sm:text-lg [&_a]:font-bold [&_a]:text-gold [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-gold [&_blockquote]:pl-4 [&_h2]:font-bold [&_h2]:text-white [&_h3]:font-bold [&_h3]:text-white [&_li]:ml-5 [&_li]:list-disc [&_p+p]:mt-3"
              dangerouslySetInnerHTML={{ __html: slide.description }}
            />
          ) : (
            <p className="mt-6 max-w-2xl text-base leading-8 text-white/80 sm:text-lg">
              {copy}
            </p>
          )}
        </div>
      </div>

      {slides.length > 1 ? (
        <div className="absolute right-5 bottom-6 flex items-center gap-2 sm:right-8">
          <Button
            size="icon"
            variant="outline"
            className="border-white/40 bg-[#112b48]/55 text-white hover:bg-white hover:text-[#112b48]"
            onClick={() => move(-1)}
            aria-label="Previous homepage slide"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="min-w-14 text-center text-[.68rem] font-bold text-white/80">
            {active + 1} / {slides.length}
          </span>
          <Button
            size="icon"
            variant="outline"
            className="border-white/40 bg-[#112b48]/55 text-white hover:bg-white hover:text-[#112b48]"
            onClick={() => move(1)}
            aria-label="Next homepage slide"
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      ) : null}
      <div className="absolute right-0 bottom-0 left-0 h-1 bg-gold" />
    </section>
  );
}
