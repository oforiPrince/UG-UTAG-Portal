import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdSlotBanner } from "@/components/public/ad-slot-banner";

describe("AdSlotBanner", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders a page-aware fluid advertisement from the public ads API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/api/v1/public/ads/footer")) {
          return {
            ok: true,
            json: async () => [
              {
                id: "camp-1",
                title: "Footer sponsor",
                media_asset_id: "media-1",
                target_url: "https://example.edu.gh",
                width: 970,
                height: 90,
              },
            ],
          };
        }
        return { ok: true, json: async () => ({}) };
      }),
    );

    render(<AdSlotBanner slotKey="footer" context="footer" />);

    await waitFor(() => {
      expect(screen.getByLabelText("Advertisement")).toBeTruthy();
    });
    const image = screen.getByRole("img", { name: "Footer sponsor" });
    expect(image.getAttribute("width")).toBe("970");
    expect(image.getAttribute("height")).toBe("90");
    expect(screen.getByText("Sponsored")).toBeTruthy();
    const unit = screen.getByLabelText("Advertisement");
    expect(unit.getAttribute("data-ad-context")).toBe("footer");
    expect(unit.getAttribute("data-ad-slot")).toBe("footer");
  });

  it("collapses when the placement has no live campaign", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => [],
      })),
    );

    const { container } = render(
      <AdSlotBanner slotKey="home-after-hero" context="home" />,
    );
    await waitFor(() => {
      expect(screen.queryByLabelText("Advertisement")).toBeNull();
    });
    expect(container.innerHTML).toBe("");
  });

  it("rotates stably among multiple live creatives for a placement", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => [
          {
            id: "a",
            title: "Alpha",
            media_asset_id: "m1",
            target_url: null,
            width: 300,
            height: 250,
          },
          {
            id: "b",
            title: "Beta",
            media_asset_id: "m2",
            target_url: null,
            width: 300,
            height: 250,
          },
        ],
      })),
    );

    const { rerender } = render(
      <AdSlotBanner slotKey="news-sidebar" context="listing-rail" />,
    );
    await waitFor(() => {
      expect(screen.getByLabelText("Advertisement")).toBeTruthy();
    });
    const first = screen.getByRole("img").getAttribute("alt");
    rerender(<AdSlotBanner slotKey="news-sidebar" context="listing-rail" />);
    await waitFor(() => {
      expect(screen.getByRole("img").getAttribute("alt")).toBe(first);
    });
  });
});
