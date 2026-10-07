import { describe, expect, it } from "vitest";

import {
  isNavigationHrefActive,
  navigation,
  navigationItemForPath,
} from "@/lib/navigation";

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

  it("keeps a nested gallery page in the Galleries section", () => {
    const item = navigationItemForPath(
      navigation,
      "/dashboard/galleries/gallery-1/edit",
    );

    expect(item?.label).toBe("Galleries");
    expect(
      isNavigationHrefActive(
        "/dashboard/galleries",
        "/dashboard/galleries/gallery-1/edit",
      ),
    ).toBe(true);
    expect(
      isNavigationHrefActive(
        "/dashboard",
        "/dashboard/galleries/gallery-1/edit",
      ),
    ).toBe(false);
  });

  it("keeps order detail pages in the Adverts section", () => {
    const pathname = "/dashboard/advert-orders/order-1/edit";

    expect(navigationItemForPath(navigation, pathname)?.label).toBe("Adverts");
    expect(isNavigationHrefActive("/dashboard/adverts", pathname)).toBe(true);
  });
});
