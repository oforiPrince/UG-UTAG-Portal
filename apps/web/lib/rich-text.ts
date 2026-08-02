const EMPTY_HTML = new Set(["", "<p></p>"]);

export function normalizeEditorHtml(value: string) {
  return EMPTY_HTML.has(value.trim()) ? "" : value;
}

export function normalizeLinkHref(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (
    /^[a-z][a-z0-9+.-]*:/i.test(trimmed) &&
    !/^(https?:|mailto:)/i.test(trimmed)
  ) {
    return null;
  }

  const candidate = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)
    ? `mailto:${trimmed}`
    : /^(https?:|mailto:)/i.test(trimmed)
      ? trimmed
      : `https://${trimmed}`;

  try {
    const url = new URL(candidate);
    if (!["http:", "https:", "mailto:"].includes(url.protocol)) return null;
    if (url.protocol === "mailto:" && !url.pathname.includes("@")) return null;
    return candidate;
  } catch {
    return null;
  }
}
