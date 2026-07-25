import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { publicApi } from "@/lib/api";

import GalleryPage from "./page";

vi.mock("@/lib/api", () => ({ publicApi: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/gallery" }));

describe("public gallery content", () => {
  it("renders the formatted gallery introduction without exposing HTML tags", async () => {
    vi.mocked(publicApi).mockResolvedValue([
      {
        id: "gallery-1",
        slug: "member-forum",
        title: "Member forum",
        description:
          "<p>Photographs from our <strong>annual forum</strong>.</p>",
        image_count: 0,
        external_album_url: null,
        images: [],
      },
    ]);

    const { container } = render(await GalleryPage());

    expect((await screen.findByText("annual forum")).tagName).toBe("STRONG");
    expect(container.textContent).not.toContain("<strong>");
  });
});
