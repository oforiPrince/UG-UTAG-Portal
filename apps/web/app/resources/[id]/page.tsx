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
      <main className="mx-auto max-w-[92rem] px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
        <DocumentPreview
          document={publicDocumentPreview(document)}
          backHref="/resources"
          backLabel="All resources"
        />
      </main>
    </PublicShell>
  );
}
