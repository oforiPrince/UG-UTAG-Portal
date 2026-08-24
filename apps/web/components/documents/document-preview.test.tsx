import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DocumentPreviewData } from "@/lib/documents";

import { DocumentPreview } from "./document-preview";

const document: DocumentPreviewData = {
  id: "document-1",
  reference: "UTAG-DOC-001",
  title: "Theme-safe document",
  sender: "UTAG UG Secretariat",
  receiver: "All members",
  descriptionHtml: "<p>Readable document description</p>",
  documentDate: "2026-08-24",
  files: [],
  details: [{ label: "Category", value: "Circular" }],
};

describe("DocumentPreview", () => {
  it("uses semantic surfaces and themed rich text in an empty preview", () => {
    render(<DocumentPreview document={document} privateView embedded />);

    const article = screen.getByRole("article");
    expect(article.className).toContain("bg-paper");
    expect(article.className).not.toContain("bg-white");
    expect(screen.getByText("Theme-safe document").className).toContain(
      "text-ink",
    );

    const richText = screen.getByText(
      "Readable document description",
    ).parentElement;
    expect(richText?.className).toContain("themed-prose");
    expect(
      screen.getByText("No preview file is attached.").parentElement
        ?.parentElement?.className,
    ).toContain("bg-panel");
  });
});
