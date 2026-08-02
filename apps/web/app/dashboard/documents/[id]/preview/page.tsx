import type { Metadata } from "next";

import { MemberDocumentPreviewClient } from "./preview-client";

export const metadata: Metadata = { title: "Document preview" };

export default async function MemberDocumentPreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MemberDocumentPreviewClient id={id} />;
}
