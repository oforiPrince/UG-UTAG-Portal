import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DocumentPreview } from "@/components/documents/document-preview";
import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";
import { type PublicDocument, publicDocumentPreview } from "@/lib/documents";

export const metadata: Metadata = { title: "Document preview" };

export default async function PublicDocumentPreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const document = await publicApi<PublicDocument | null>(
    `/api/v1/public/documents/${encodeURIComponent(id)}`,
    null,
    { revalidate: false },
  );
  if (!document) notFound();

  return (
    <PublicShell>
      <div className="mx-auto w-full min-w-0 max-w-[92rem] px-4 py-8 sm:px-6 sm:py-12 lg:px-8 lg:py-14">
        <DocumentPreview
          document={publicDocumentPreview(document)}
          backHref="/resources"
          backLabel="All resources"
        />
      </div>
    </PublicShell>
  );
}
