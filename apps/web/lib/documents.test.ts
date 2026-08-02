import { describe, expect, it } from "vitest";

import {
  documentPreviewKind,
  memberDocumentPreview,
  publicDocumentPreview,
} from "./documents";

describe("document previews", () => {
  it.each([
    ["application/pdf", "pdf"],
    ["image/png", "image"],
    ["text/plain", "text"],
    [
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "office",
    ],
    ["application/octet-stream", "unknown"],
  ])("classifies %s as %s", (contentType, expected) => {
    expect(documentPreviewKind(contentType)).toBe(expected);
  });

  it("keeps every public file available in the preview", () => {
    const preview = publicDocumentPreview({
      id: "document-1",
      public_id: "UTAG-001",
      title: "Public policy",
      sender: "UTAG",
      receiver: "General public",
      description_html: "<p>Complete public description.</p>",
      document_date: "2026-08-02",
      filename: "policy.pdf",
      content_type: "application/pdf",
      byte_size: 2_048,
      download_url: "/api/v1/public/media/file-1",
      files: [
        {
          media_asset_id: "file-1",
          filename: "policy.pdf",
          content_type: "application/pdf",
          byte_size: 2_048,
          download_url: "/api/v1/public/media/file-1",
        },
        {
          media_asset_id: "file-2",
          filename: "appendix.csv",
          content_type: "text/csv",
          byte_size: 1_024,
          content_url: "/api/v1/public/media/file-2/content",
          download_url: "/api/v1/public/media/file-2",
        },
      ],
    });

    expect(preview.files).toHaveLength(2);
    expect(preview.files.map((file) => file.contentUrl)).toEqual([
      "/api/v1/public/media/file-1",
      "/api/v1/public/media/file-2/content",
    ]);
    expect(preview.descriptionHtml).toContain("Complete public description");
  });

  it("shows protected visibility and compliance details to members", () => {
    const preview = memberDocumentPreview({
      id: "document-2",
      public_id: "UTAG-002",
      title: "Member circular",
      category: "internal",
      sender: null,
      receiver: null,
      description_html: "<p>Full circular.</p>",
      document_date: null,
      status: "published",
      audiences: [
        { type: "all_members", value: "all" },
        { type: "role", value: "executive" },
      ],
      retention_class: "governance",
      legal_hold: true,
      version: 3,
      files: [
        {
          media_asset_id: "file-3",
          filename: "circular.pdf",
          content_type: "application/pdf",
          byte_size: 4_096,
          content_url: "/api/v1/documents/document-2/files/file-3/content",
        },
      ],
    });

    expect(preview.details).toEqual(
      expect.arrayContaining([
        { label: "Visible to", value: "All members, Executive" },
        { label: "Version", value: "3" },
        { label: "Retention class", value: "governance" },
        { label: "Legal hold", value: "Enabled" },
      ]),
    );
  });
});
