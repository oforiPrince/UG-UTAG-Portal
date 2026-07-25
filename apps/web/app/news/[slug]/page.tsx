import { format } from "date-fns";
import {
  ArrowDownToLine,
  ArrowLeft,
  CalendarDays,
  FileText,
} from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";

type Article = {
  slug: string;
  title: string;
  excerpt: string;
  content_html: string;
  tags: string[];
  citations: { source_name?: string; url: string }[];
  published_at: string | null;
  featured_media_id: string | null;
  attachments: {
    media_asset_id: string;
    filename: string;
    content_type: string;
    byte_size: number;
    content_url: string;
  }[];
};

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const article = await publicApi<Article | null>(
    `/api/v1/public/articles/${encodeURIComponent(slug)}`,
    null,
    { revalidate: false },
  );
  if (!article) notFound();
  return (
    <PublicShell>
      <header className="relative isolate overflow-hidden bg-[#122b48] text-white">
        <div
          className="absolute inset-0 -z-20 bg-cover bg-center"
          style={{
            backgroundImage: `url('${
              article.featured_media_id
                ? `/api/v1/public/media/${article.featured_media_id}`
                : "/brand/hero-meeting.jpg"
            }')`,
          }}
        />
        <div className="absolute inset-0 -z-10 bg-[#0d2947]/90" />
        <div className="mx-auto max-w-[82rem] px-5 py-14 sm:px-6 sm:py-18 lg:px-8 lg:py-20">
          <Link
            href="/news"
            className="inline-flex items-center gap-2 text-xs font-bold text-white/72 hover:text-white"
          >
            <ArrowLeft className="size-4" /> Back to news
          </Link>
          <p className="mt-8 text-[.7rem] font-extrabold tracking-[.14em] text-gold uppercase">
            {article.tags[0] ?? "Association news"}
          </p>
          <h1 className="display-type mt-4 max-w-5xl text-4xl leading-tight text-white sm:text-5xl lg:text-6xl">
            {article.title}
          </h1>
          <p className="mt-5 max-w-3xl text-base leading-8 text-white/76">
            {article.excerpt}
          </p>
          <p className="mt-6 inline-flex items-center gap-2 text-xs font-bold text-white/65">
            <CalendarDays className="size-4 text-gold" />
            {article.published_at
              ? format(new Date(article.published_at), "d MMMM yyyy")
              : "UG UTAG"}
          </p>
        </div>
        <div className="h-1 bg-gold" />
      </header>
      <article className="mx-auto max-w-4xl px-5 py-14 sm:px-6 lg:py-18">
        <div
          className="prose prose-lg max-w-none text-ink prose-headings:text-[#172f4d] prose-headings:font-bold prose-a:text-coral prose-a:font-semibold"
          dangerouslySetInnerHTML={{ __html: article.content_html }}
        />
        {article.attachments.length ? (
          <section className="mt-12 border-t border-line pt-8">
            <h2 className="text-xl font-black text-[#172f4d]">
              Supporting documents
            </h2>
            <div className="mt-4 grid gap-3">
              {article.attachments.map((attachment) => (
                <a
                  key={attachment.media_asset_id}
                  href={attachment.content_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-4 rounded-md border border-line bg-panel p-4 transition hover:border-coral/35"
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-white text-coral">
                    <FileText className="size-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <b className="block truncate text-sm">
                      {attachment.filename}
                    </b>
                    <span className="mt-1 block text-xs text-muted">
                      Supporting file
                    </span>
                  </span>
                  <ArrowDownToLine className="size-4 text-coral" />
                </a>
              ))}
            </div>
          </section>
        ) : null}
      </article>
    </PublicShell>
  );
}
