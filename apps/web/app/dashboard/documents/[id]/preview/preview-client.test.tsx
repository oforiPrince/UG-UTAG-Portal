import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { MemberDocumentPreviewClient } from "./preview-client";

vi.mock("@/lib/api", () => ({ api: vi.fn() }));
vi.mock("@/components/documents/document-preview", () => ({
  DocumentPreview: ({
    document,
    privateView,
  }: {
    document: { title: string; files: { filename: string }[] };
    privateView: boolean;
  }) => (
    <div>
      <h1>{document.title}</h1>
      <span>{privateView ? "Protected preview" : "Public preview"}</span>
      {document.files.map((file) => (
        <span key={file.filename}>{file.filename}</span>
      ))}
    </div>
  ),
}));

describe("member document preview", () => {
  it("loads the authorized document and includes every current file", async () => {
    vi.mocked(api).mockResolvedValue({
      id: "document-1",
      public_id: "UTAG-001",
      title: "Member circular",
      category: "internal",
      sender: null,
      receiver: null,
      description_html: "<p>Complete circular.</p>",
      document_date: null,
      status: "published",
      audiences: [{ type: "all_members", value: "all" }],
      retention_class: null,
      legal_hold: false,
      version: 1,
      files: [
        {
          media_asset_id: "file-1",
          filename: "circular.pdf",
          content_type: "application/pdf",
          byte_size: 2_048,
          content_url: "/api/v1/documents/document-1/files/version-1/content",
        },
        {
          media_asset_id: "file-2",
          filename: "appendix.txt",
          content_type: "text/plain",
          byte_size: 512,
          content_url: "/api/v1/documents/document-1/files/version-2/content",
        },
      ],
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemberDocumentPreviewClient id="document-1" />
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Member circular" }),
      ).toBeTruthy(),
    );
    expect(screen.getByText("Protected preview")).toBeTruthy();
    expect(screen.getByText("circular.pdf")).toBeTruthy();
    expect(screen.getByText("appendix.txt")).toBeTruthy();
    expect(api).toHaveBeenCalledWith("/api/v1/documents/document-1");
  });
});
