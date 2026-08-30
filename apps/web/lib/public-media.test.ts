import { describe, expect, it } from "vitest";

import { publicMediaUrl } from "@/lib/public-media";

describe("publicMediaUrl", () => {
  it("returns null without an asset id", () => {
    expect(publicMediaUrl(null)).toBeNull();
    expect(publicMediaUrl(undefined)).toBeNull();
  });

  it("appends sized variants by default", () => {
    expect(publicMediaUrl("asset-1")).toBe("/api/v1/public/media/asset-1?v=w960");
    expect(publicMediaUrl("asset-1", "w480")).toBe(
      "/api/v1/public/media/asset-1?v=w480",
    );
  });

  it("keeps originals unversioned", () => {
    expect(publicMediaUrl("asset-1", "original")).toBe(
      "/api/v1/public/media/asset-1",
    );
  });
});
