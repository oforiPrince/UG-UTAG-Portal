import { format } from "date-fns";
import { ArrowDownToLine, Eye, FileText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageHero } from "@/components/public/page-hero";
import { PublicEmptyState } from "@/components/public/public-empty-state";
import { PublicShell } from "@/components/public/public-shell";
import { Button } from "@/components/ui/button";
import { publicApi } from "@/lib/api";
import { type PublicDocument, fileSize } from "@/lib/documents";

export const metadata: Metadata = { title: "Resources" };

export default async function ResourcesPage() {
  const documents = await publicApi<PublicDocument[]>(
    "/api/v1/public/documents",
    [],
    { revalidate: false },
  );
  return (
    <PublicShell>
      <PageHero
        eyebrow="Resources"
        title="Public documents and association resources"
        intro="Constitutional, policy, and public-interest material approved for public access by the University of Ghana Branch of UTAG."
      />
      <section className="mx-auto w-full min-w-0 max-w-[82rem] px-4 py-12 sm:px-6 sm:py-16 lg:px-8 lg:py-22">
        {documents.length === 0 ? (
          <PublicEmptyState
            title="No public documents have been released"
            description="Documents appear here only after they pass review and are explicitly published as external resources."
          />
        ) : (
          <div className="grid w-full min-w-0 gap-4 sm:gap-5 md:grid-cols-2 lg:grid-cols-3">
            {documents.map((document) => (
              <article
                id={document.id}
                key={document.id}
                className="flex min-w-0 flex-col overflow-hidden rounded-md border border-line bg-white p-4 shadow-[0_8px_26px_rgb(23_43_69_/_7%)] sm:p-6 lg:p-7"
              >
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#edf3f8] text-coral sm:size-12">
                  <FileText className="size-5" />
                </span>
                <h2 className="mt-5 text-lg font-extrabold leading-snug break-words text-[#172f4d] sm:mt-6 sm:text-xl">
                  {document.title}
                </h2>
                {document.description_html ? (
                  <div
                    className="mt-3 line-clamp-3 text-sm leading-6 break-words text-muted"
                    dangerouslySetInnerHTML={{
                      __html: document.description_html,
                    }}
                  />
                ) : null}
                <div className="mt-5 flex flex-wrap gap-x-4 gap-y-2 border-t border-line pt-4 text-[.68rem] font-semibold text-muted sm:mt-6">
                  {document.document_date ? (
                    <time dateTime={document.document_date}>
                      {format(new Date(document.document_date), "d MMM yyyy")}
                    </time>
                  ) : null}
                  <span>
                    {document.files.length} file
                    {document.files.length === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mt-4 grid min-w-0 gap-2 sm:mt-5">
                  <Button
                    asChild
                    className="flex w-full min-w-0 max-w-full overflow-hidden rounded-md px-3 sm:px-5"
                  >
                    <Link href={`/resources/${document.id}`}>
                      <Eye className="size-4 shrink-0" />
                      <span className="truncate">Preview full document</span>
                    </Link>
                  </Button>
                  {document.files.map((file) => (
                    <Button
                      key={file.media_asset_id}
                      asChild
                      className="flex w-full min-w-0 max-w-full justify-between gap-2 overflow-hidden rounded-md px-3 sm:gap-3 sm:px-5"
                      variant="outline"
                    >
                      <a href={file.download_url} download={file.filename}>
                        <span className="min-w-0 flex-1 truncate text-left">
                          {file.filename}
                        </span>
                        <span className="inline-flex shrink-0 items-center gap-1.5 text-xs sm:gap-2">
                          {fileSize(file.byte_size)}
                          <ArrowDownToLine className="size-4" />
                        </span>
                      </a>
                    </Button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </PublicShell>
  );
}
