import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function humanize(value: string) {
  return value.replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const HONORIFIC_PREFIX =
  /^(dr|prof|professor|mr|mrs|ms|miss|rev|sir|madam)\.?\s+/i;

function alphabeticChars(value: string) {
  return [...value].filter((char) => /[a-zA-Z]/.test(char));
}

function nameBodyForCase(reference: string) {
  return reference.replace(HONORIFIC_PREFIX, "").trim() || reference.trim();
}

/** Apply the casing style of `reference` (usually a person name) to `value`. */
export function matchCaseStyle(reference: string, value: string): string {
  const trimmed = value.trim();
  if (!trimmed || !reference.trim()) return value;

  const letters = alphabeticChars(nameBodyForCase(reference));
  if (letters.length === 0) return value;

  const upperRatio =
    letters.filter((char) => char === char.toUpperCase()).length /
    letters.length;

  if (upperRatio >= 0.85) {
    return trimmed.toUpperCase();
  }

  const lowerRatio =
    letters.filter((char) => char === char.toLowerCase()).length /
    letters.length;
  if (lowerRatio >= 0.85) {
    return trimmed.toLowerCase();
  }

  return humanize(trimmed.toLowerCase().replace(/\s+/g, " "));
}

/** Keep academic rank / title casing aligned with the person name. */
export function formatRankForName(
  fullName: string | null | undefined,
  rank: string | null | undefined,
): string {
  if (!rank?.trim()) return "";
  if (!fullName?.trim()) return rank;
  return matchCaseStyle(fullName, rank);
}

/** Align honorific casing (Dr./Prof.) with the rest of the name. */
export function formatPersonName(fullName: string | null | undefined): string {
  if (!fullName?.trim()) return fullName ?? "";
  const match = fullName.trim().match(
    /^(dr|prof|professor|mr|mrs|ms|miss|rev|sir|madam)(\.?)(\s+)(.+)$/i,
  );
  if (!match) return fullName;
  const [, honorific, dot, space, rest] = match;
  return `${matchCaseStyle(rest, honorific)}${dot}${space}${rest}`;
}

export function formatNumber(value: number | string) {
  return new Intl.NumberFormat("en-GH", { notation: "compact" }).format(Number(value));
}
