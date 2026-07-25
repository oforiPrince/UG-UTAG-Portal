import { format } from "date-fns";
import { ArrowDownToLine, FileText, LockKeyhole } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageHero } from "@/components/public/page-hero";
import { PublicEmptyState } from "@/components/public/public-empty-state";
import { PublicShell } from "@/components/public/public-shell";
import { Button } from "@/components/ui/button";
import { publicApi } from "@/lib/api";

export const metadata: Metadata = { title: "Resources" };

type PublicDocument = {
  id: string;
  public_id: string;
  title: string;
  sender: string | null;
  receiver: string | null;
  description_html: string;
  document_date: string | null;
  filename: string;
  content_type: string;
  byte_size: number;
  download_url: string;
  files: {
    media_asset_id: string;
    filename: string;
    content_type: string;
    byte_size: number;
    download_url: string;
  }[];
};

function fileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default async function ResourcesPage() {
  const documents = await publicApi<PublicDocument[]>(
    "/api/v1/public/documents",
    [],
  );
  return (
    <PublicShell>
      <PageHero
        eyebrow="Resources"
        title="Public documents and association resources"
        intro="Constitutional, policy and public-interest material approved for public access by the University of Ghana Branch of UTAG."
      />
      <section className="mx-auto max-w-[82rem] px-5 py-16 sm:px-6 lg:px-8 lg:py-22">
        {documents.length === 0 ? (
          <PublicEmptyState
            title="No public documents have been released"
            description="Documents appear here only after they pass review and are explicitly published as external resources."
          />
        ) : (
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {documents.map((document) => (
              <article
                id={document.id}
                key={document.id}
                className="scroll-mt-32 rounded-md border border-line bg-white p-7 shadow-[0_8px_26px_rgb(23_43_69_/_7%)]"
              >
                <div className="flex items-start justify-between gap-5">
                  <span className="grid size-13 shrink-0 place-items-center rounded-full bg-[#edf3f8] text-coral">
                    <FileText className="size-6" />
                  </span>
                  <span className="rounded-full bg-[#f5f8fb] px-3 py-1.5 text-[.62rem] font-extrabold text-muted uppercase">
                    {document.public_id}
                  </span>
                </div>
                <h2 className="mt-7 text-xl font-extrabold leading-snug text-[#172f4d]">
                  {document.title}
                </h2>
                {document.description_html ? (
                  <div
                    className="mt-3 line-clamp-3 text-sm leading-6 text-muted"
                    dangerouslySetInnerHTML={{
                      __html: document.description_html,
                    }}
                  />
                ) : null}
                <div className="mt-6 flex flex-wrap gap-x-4 gap-y-2 border-t border-line pt-4 text-[.68rem] font-semibold text-muted">
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
                <div className="mt-5 grid gap-2">
                  {document.files.map((file) => (
                    <Button
                      key={file.media_asset_id}
                      asChild
                      className="w-full justify-between rounded-md"
                      variant="outline"
                    >
                      <a
                        href={file.download_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <span className="min-w-0 truncate">
                          {file.filename}
                        </span>
                        <span className="inline-flex shrink-0 items-center gap-2 text-xs">
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
      <section className="mx-auto max-w-[82rem] px-5 sm:px-6 lg:px-8">
        <div className="grid gap-7 border-l-4 border-gold bg-[#172f4d] p-8 text-white sm:p-10 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <p className="text-[.7rem] font-extrabold tracking-[.14em] text-gold uppercase">
              Member library
            </p>
            <h2 className="display-type mt-3 text-2xl sm:text-3xl">
              Internal documents remain protected in the secure portal.
            </h2>
          </div>
          <Button asChild className="rounded-md" variant="gold">
            <Link href="/login">
              <LockKeyhole className="size-4" /> Member access
            </Link>
          </Button>
        </div>
      </section>
    </PublicShell>
  );
}
