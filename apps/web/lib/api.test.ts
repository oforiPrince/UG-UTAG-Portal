import { afterEach, describe, expect, it, vi } from "vitest";

import { normalizeApiUrl, publicApi } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("normalizeApiUrl", () => {
  it("uses the same origin when the public URL is blank", () => {
    expect(normalizeApiUrl(undefined)).toBe("");
    expect(normalizeApiUrl("   ")).toBe("");
  });

  it("removes trailing slashes from configured origins", () => {
    expect(normalizeApiUrl(" https://portal.example/api/// ")).toBe(
      "https://portal.example/api",
    );
  });
});

describe("publicApi", () => {
  it("can bypass the public fetch cache for immediately visible content", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ full_name: "Updated executive" })),
      );

    await publicApi("/api/v1/public/leadership", {}, { revalidate: false });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/public/leadership"),
      { cache: "no-store" },
    );
  });

  it("keeps the normal short revalidation window by default", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify([])));

    await publicApi("/api/v1/public/events", []);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/public/events"),
      { next: { revalidate: 30 } },
    );
  });
});
