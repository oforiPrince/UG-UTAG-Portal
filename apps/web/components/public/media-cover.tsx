import type { ReactNode } from "react";

import { publicMediaUrl, type PublicMediaVariant } from "@/lib/public-media";
import { cn } from "@/lib/utils";

type MediaCoverProps = {
  assetId?: string | null;
  fallbackSrc?: string;
  alt?: string;
  className?: string;
  imageClassName?: string;
  variant?: PublicMediaVariant;
  priority?: boolean;
  children?: ReactNode;
};

/** Responsive cover image that lazy-loads by default and prefers WebP variants. */
export function MediaCover({
  assetId,
  fallbackSrc = "/brand/hero-meeting.jpg",
  alt = "",
  className,
  imageClassName,
  variant = "w960",
  priority = false,
  children,
}: MediaCoverProps) {
  const src = publicMediaUrl(assetId, variant) ?? fallbackSrc;

  return (
    <div className={cn("relative overflow-hidden bg-[#d7e0ea]", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        className={cn("absolute inset-0 size-full object-cover", imageClassName)}
        loading={priority ? "eager" : "lazy"}
        decoding="async"
        fetchPriority={priority ? "high" : "auto"}
        sizes={
          variant === "w480"
            ? "(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
            : variant === "w1600"
              ? "100vw"
              : "(min-width: 1024px) 50vw, 100vw"
        }
      />
      {children}
    </div>
  );
}
