import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { publicApi } from "@/lib/api";

import PublicDocumentPreviewPage from "./page";

vi.mock("@/lib/api", () => ({ publicApi: vi.fn() }));
vi.mock("@/components/public/public-shell", () => ({
  PublicShell: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("@/components/documents/document-preview", () => ({
  DocumentPreview: ({
    document,
  }: {
    document: { title: string; files: { filename: string }[] };
  }) => (
    <div>
      <h1>{document.title}</h1>
      {document.files.map((file) => (
        <span key={file.filename}>{file.filename}</span>
      ))}
    </div>
  ),
}));

describe("public document preview page", () => {
  it("loads the selected public document and every attached file", async () => {
    vi.mocked(publicApi).mockResolvedValue({
      id: "document-1",
      public_id: "UTAG-001",
      title: "Public policy brief",
      sender: null,
      receiver: null,
      description_html: "<p>Complete guidance.</p>",
      document_date: "2026-08-02",
      filename: "policy.pdf",
      content_type: "application/pdf",
      byte_size: 2_048,
      content_url: "/api/v1/public/media/file-1",
      download_url: "/api/v1/public/media/file-1",
      files: [
        {
          media_asset_id: "file-1",
          filename: "policy.pdf",
          content_type: "application/pdf",
          byte_size: 2_048,
          content_url: "/api/v1/public/media/file-1",
          download_url: "/api/v1/public/media/file-1",
        },
        {
          media_asset_id: "file-2",
          filename: "appendix.txt",
          content_type: "text/plain",
          byte_size: 512,
          content_url: "/api/v1/public/media/file-2",
          download_url: "/api/v1/public/media/file-2",
        },
      ],
    });

    render(
      await PublicDocumentPreviewPage({
        params: Promise.resolve({ id: "document-1" }),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Public policy brief" }),
    ).toBeTruthy();
    expect(screen.getByText("policy.pdf")).toBeTruthy();
    expect(screen.getByText("appendix.txt")).toBeTruthy();
    expect(publicApi).toHaveBeenCalledWith(
      "/api/v1/public/documents/document-1",
      null,
      { revalidate: false },
    );
  });
});
