import { afterEach, describe, expect, it, vi } from "vitest";

import { publicApiResult } from "./api";
import { getPublicSite, phoneHref } from "./public-site";

vi.mock("./api", () => ({ publicApiResult: vi.fn() }));

afterEach(() => {
  vi.clearAllMocks();
});

describe("public site contact settings", () => {
  it("creates a callable international number from the displayed Ghana format", () => {
    expect(phoneHref("+233 (0) 24 427 7275")).toBe("+233244277275");
  });

  it("uses the official contact details when stored values are empty", async () => {
    vi.mocked(publicApiResult)
      .mockResolvedValueOnce({
        data: {
          "site.contact": {
            email: "",
            phone: "   ",
            address: "University of Ghana, Legon, Accra",
          },
        },
        unavailable: false,
      })
      .mockResolvedValueOnce({
        data: {
          "association-pulse": true,
          "public-resources": true,
          "public-gallery": true,
        },
        unavailable: false,
      });

    const site = await getPublicSite();

    expect(site.contact.email).toBe("utagoffice@ug.edu.gh");
    expect(site.contact.phone).toBe("+233 (0) 24 427 7275");
  });

  it("trims configured contact details before displaying them", async () => {
    vi.mocked(publicApiResult)
      .mockResolvedValueOnce({
        data: {
          "site.contact": {
            email: " secretariat@example.edu.gh ",
            phone: " +233 20 000 0000 ",
          },
        },
        unavailable: false,
      })
      .mockResolvedValueOnce({
        data: {
          "association-pulse": true,
          "public-resources": true,
          "public-gallery": true,
        },
        unavailable: false,
      });

    const site = await getPublicSite();

    expect(site.contact.email).toBe("secretariat@example.edu.gh");
    expect(site.contact.phone).toBe("+233 20 000 0000");
  });
});
