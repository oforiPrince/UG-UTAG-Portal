import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { WorkspacePanelPreview } from "./workspace-panel-preview";

vi.mock("@/lib/api", () => ({ api: vi.fn() }));

describe("WorkspacePanelPreview", () => {
  it("uses semantic surfaces and themed rich text for article previews", async () => {
    vi.mocked(api).mockResolvedValue({
      id: "news-1",
      kind: "news",
      title: "Theme-safe article",
      summary: "A preview that remains readable in either theme.",
      body_html: "<h2>Readable heading</h2><p>Readable body</p>",
      status: "published",
      media_asset_ids: [],
      details: { tags: "association_news" },
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <WorkspacePanelPreview
          kind="news"
          row={{ id: "news-1" }}
          onBack={vi.fn()}
        />
      </QueryClientProvider>,
    );

    const article = await screen.findByRole("article");
    expect(article.className).toContain("bg-paper");
    expect(article.className).not.toContain("bg-white");

    const richText = screen.getByText("Readable body").parentElement;
    expect(richText?.className).toContain("themed-prose");
  });
});
