export type PublicMediaVariant = "w480" | "w960" | "w1600" | "original";

/** Same-origin public media URL with an optional sized WebP variant. */
export function publicMediaUrl(
  assetId: string | null | undefined,
  variant: PublicMediaVariant = "w960",
): string | null {
  if (!assetId) return null;
  const base = `/api/v1/public/media/${assetId}`;
  if (variant === "original") return base;
  return `${base}?v=${variant}`;
}
