import { describe, expect, it } from "vitest";

import { navigation } from "@/lib/navigation";

describe("advert navigation", () => {
  it("exposes a single Adverts sidebar entry", () => {
    const advertItems = navigation.filter((item) =>
      item.href.startsWith("/dashboard/advert"),
    );
    expect(advertItems).toEqual([
      expect.objectContaining({
        label: "Adverts",
        href: "/dashboard/adverts",
        permission: "adverts.manage",
      }),
    ]);
  });
});
