import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { GalleryDetailClient } from "./gallery-detail-client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: vi.fn() };
});

afterEach(cleanup);

describe("gallery dashboard detail page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows an image-led detail page without dumping media filenames", async () => {
    vi.mocked(api).mockImplementation((async (path: string) => {
      if (path === "/api/v1/auth/me") {
        return { permissions: ["content.view", "content.edit"] };
      }
      return {
        id: "gallery-1",
        slug: "annual-forum",
        title: "Annual forum",
        description:
          "<p>Photographs from the <strong>opening day</strong>.</p>",
        external_album_url: "https://drive.google.com/example",
        status: "published",
        published_at: "2026-08-03T06:44:00Z",
        created_at: "2026-08-02T06:44:00Z",
        updated_at: "2026-08-03T06:44:00Z",
        version: 3,
        items: [
          {
            id: "item-1",
            media_asset_id: "media-1",
            media_name: "very-long-camera-filename-001.jpg",
            position: 0,
            caption: "Members arriving for the forum",
            allow_download: true,
          },
          {
            id: "item-2",
            media_asset_id: "media-2",
            media_name: "very-long-camera-filename-002.jpg",
            position: 1,
            caption: null,
            allow_download: false,
          },
        ],
      };
    }) as typeof api);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <GalleryDetailClient galleryId="gallery-1" />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Annual forum" }),
    ).toBeTruthy();
    expect(screen.getByText("Photo 01")).toBeTruthy();
    expect(screen.getByText("View only")).toBeTruthy();
    expect(screen.getByText("opening day").tagName).toBe("STRONG");
    expect(container.textContent).not.toContain("very-long-camera-filename");
    expect(
      screen.getByRole("link", { name: "Edit gallery" }).getAttribute("href"),
    ).toBe("/dashboard/galleries/gallery-1/edit");
    expect(screen.queryByRole("button", { name: "Delete gallery" })).toBeNull();
  });

  it("offers a consequence-aware delete action to records administrators", async () => {
    vi.mocked(api).mockImplementation((async (path: string) => {
      if (path === "/api/v1/auth/me") {
        return { permissions: ["content.view", "content.edit", "records.delete"] };
      }
      return {
        id: "gallery-1",
        slug: "annual-forum",
        title: "Annual forum",
        description: "",
        external_album_url: null,
        status: "draft",
        published_at: null,
        created_at: "2026-08-02T06:44:00Z",
        updated_at: "2026-08-03T06:44:00Z",
        version: 1,
        items: [],
      };
    }) as typeof api);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <GalleryDetailClient galleryId="gallery-1" />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole("button", { name: "Delete gallery" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Add images" }).getAttribute("href"),
    ).toBe("/dashboard/galleries/gallery-1/edit");
  });
});
