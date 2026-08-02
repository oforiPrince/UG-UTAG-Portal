import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { publicApi } from "@/lib/api";

import ResourcesPage from "./page";

vi.mock("@/lib/api", () => ({ publicApi: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/resources" }));
vi.mock("@/components/public/public-shell", () => ({
  PublicShell: ({ children }: { children: React.ReactNode }) => children,
}));

describe("public resources", () => {
  it("loads fresh public documents instead of a cached startup fallback", async () => {
    vi.mocked(publicApi).mockResolvedValue([
      {
        id: "document-1",
        public_id: "UTAG-PUBLIC",
        title: "Public policy brief",
        sender: null,
        receiver: null,
        description_html: "<p>Approved public guidance.</p>",
        document_date: "2026-08-02",
        filename: "policy.pdf",
        content_type: "application/pdf",
        byte_size: 2048,
        download_url: "/api/v1/public/media/file-1",
        files: [
          {
            media_asset_id: "file-1",
            filename: "policy.pdf",
            content_type: "application/pdf",
            byte_size: 2048,
            download_url: "/api/v1/public/media/file-1",
          },
        ],
      },
    ]);

    render(await ResourcesPage());

    expect(
      screen.getByRole("heading", { name: "Public policy brief" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "Preview full document" })
        .getAttribute("href"),
    ).toBe("/resources/document-1");
    expect(publicApi).toHaveBeenCalledWith("/api/v1/public/documents", [], {
      revalidate: false,
    });
  });
});
