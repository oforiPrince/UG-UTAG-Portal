import { format } from "date-fns";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Clock3,
  FileText,
  Quote,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PublicAttachments } from "@/components/public/public-attachments";
import { AdSlotBanner } from "@/components/public/ad-slot-banner";
import { MediaCover } from "@/components/public/media-cover";
import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";
import { publicMediaUrl } from "@/lib/public-media";

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

type RelatedArticle = {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  tags: string[];
  published_at: string | null;
  featured_media_id: string | null;
};

type Page<T> = { items: T[]; total: number };

function readingMinutes(html: string, attachmentCount: number) {
  const text = html
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const words = text ? text.split(" ").length : 0;
  const attachmentBonus = attachmentCount > 0 ? Math.min(8, attachmentCount * 4) : 0;
  return Math.max(1, Math.ceil(words / 200) + attachmentBonus);
}

function hasMeaningfulBody(html: string) {
  const text = html
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > 40;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const article = await publicApi<Article | null>(
    `/api/v1/public/articles/${encodeURIComponent(slug)}`,
    null,
    { revalidate: false },
  );
  if (!article) return { title: "News" };
  return {
    title: article.title,
    description: article.excerpt || undefined,
  };
}

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [article, listing] = await Promise.all([
    publicApi<Article | null>(
      `/api/v1/public/articles/${encodeURIComponent(slug)}`,
      null,
      { revalidate: false },
    ),
    publicApi<Page<RelatedArticle>>(
      "/api/v1/public/articles?page_size=6",
      { total: 0, items: [] },
      { revalidate: false },
    ),
  ]);
  if (!article) notFound();

  const related = listing.items
    .filter((item) => item.slug !== article.slug)
    .slice(0, 3);
  const minutes = readingMinutes(
    article.content_html,
    article.attachments.length,
  );
  const showBody = hasMeaningfulBody(article.content_html);
  const publishedLabel = article.published_at
    ? format(new Date(article.published_at), "d MMMM yyyy")
    : null;
  const category = article.tags[0] ?? "Association news";
  const heroImage =
    publicMediaUrl(article.featured_media_id, "w1600") ??
    "/brand/hero-meeting.jpg";

  return (
    <PublicShell>
      <div className="border-b border-line bg-[#f7f9fc]">
        <div className="mx-auto flex max-w-[82rem] flex-wrap items-center gap-3 px-5 py-3 text-xs font-bold text-muted sm:px-6 lg:px-8">
          <Link
            href="/news"
            className="inline-flex items-center gap-2 text-coral transition hover:text-[#172f4d]"
          >
            <ArrowLeft className="size-3.5" />
            News
          </Link>
          <span aria-hidden="true" className="text-line">
            /
          </span>
          <span className="line-clamp-1 text-[#172f4d]">{article.title}</span>
        </div>
      </div>

      <header className="mx-auto max-w-[82rem] px-5 pt-10 sm:px-6 sm:pt-14 lg:px-8">
        <div className="mx-auto max-w-3xl text-center lg:mx-0 lg:max-w-4xl lg:text-left">
          <p className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1 text-[.68rem] font-extrabold tracking-[.12em] text-coral uppercase shadow-[0_4px_16px_rgb(23_43_69_/_6%)]">
            {category}
          </p>
          <h1 className="display-type mt-5 text-[1.85rem] leading-[1.12] tracking-tight text-[#172f4d] sm:text-4xl sm:leading-[1.1] lg:text-[2.75rem]">
            {article.title}
          </h1>
          {article.excerpt ? (
            <p className="mt-5 text-base leading-8 text-muted sm:text-lg sm:leading-9">
              {article.excerpt}
            </p>
          ) : null}
          <div className="mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs font-bold text-muted lg:justify-start">
            {publishedLabel ? (
              <p className="inline-flex items-center gap-2">
                <CalendarDays className="size-3.5 text-gold" />
                <time dateTime={article.published_at ?? undefined}>
                  {publishedLabel}
                </time>
              </p>
            ) : (
              <p className="inline-flex items-center gap-2">
                <CalendarDays className="size-3.5 text-gold" />
                UG UTAG
              </p>
            )}
            <p className="inline-flex items-center gap-2">
              <Clock3 className="size-3.5 text-gold" />
              {minutes} min read
            </p>
            {article.attachments.length ? (
              <a
                href="#documents"
                className="inline-flex items-center gap-2 text-coral transition hover:text-[#172f4d]"
              >
                <FileText className="size-3.5" />
                {article.attachments.length} supporting document
                {article.attachments.length === 1 ? "" : "s"}
              </a>
            ) : null}
          </div>
        </div>

        <figure className="relative mt-10 overflow-hidden rounded-md border border-line bg-[#122b48] shadow-[0_18px_50px_rgb(23_43_69_/_12%)]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={heroImage}
            alt=""
            className="aspect-[21/9] w-full object-cover sm:aspect-[2.4/1]"
            fetchPriority="high"
            loading="eager"
            decoding="async"
            sizes="(max-width: 1280px) 100vw, 82rem"
          />
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,transparent_55%,rgba(13,41,71,.35))]" />
          <div className="absolute inset-x-0 bottom-0 h-1 bg-gold" />
        </figure>
      </header>

      <AdSlotBanner slotKey="content-inline" context="article" />

      <div className="mx-auto max-w-[82rem] px-5 py-12 sm:px-6 lg:px-8 lg:py-16">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_17.5rem] lg:items-start xl:gap-16">
          <article className="min-w-0">
            {showBody ? (
              <div
                className="prose prose-lg max-w-none text-ink prose-headings:scroll-mt-24 prose-headings:font-bold prose-headings:tracking-tight prose-headings:text-[#172f4d] prose-p:leading-8 prose-a:font-semibold prose-a:text-coral prose-blockquote:border-gold"
                dangerouslySetInnerHTML={{ __html: article.content_html }}
              />
            ) : article.excerpt ? (
              <p className="rounded-md border border-line bg-panel px-5 py-5 text-base leading-8 text-ink/85 sm:px-6">
                {article.excerpt}
              </p>
            ) : null}

            {article.attachments.length ? (
              <div className={showBody || article.excerpt ? "mt-12" : ""}>
                <PublicAttachments attachments={article.attachments} />
              </div>
            ) : null}

            {article.citations.length ? (
              <section className="mt-12 border-t border-line pt-8">
                <h2 className="flex items-center gap-2 text-sm font-extrabold tracking-wide text-[#172f4d] uppercase">
                  <Quote className="size-4 text-gold" />
                  Sources & citations
                </h2>
                <ul className="mt-4 grid gap-2">
                  {article.citations.map((citation) => (
                    <li key={citation.url}>
                      <a
                        href={citation.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-semibold text-coral underline-offset-4 hover:underline"
                      >
                        {citation.source_name || citation.url}
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {article.tags.length > 1 ? (
              <ul className="mt-10 flex flex-wrap gap-2">
                {article.tags.map((tag) => (
                  <li
                    key={tag}
                    className="rounded-full border border-line bg-panel px-3 py-1.5 text-[.68rem] font-extrabold tracking-wide text-muted uppercase"
                  >
                    {tag}
                  </li>
                ))}
              </ul>
            ) : null}
          </article>

          <aside className="lg:sticky lg:top-24">
            <div className="rounded-md border border-line bg-white p-5 shadow-[0_10px_30px_rgb(23_43_69_/_7%)]">
              <p className="text-[.68rem] font-extrabold tracking-[.14em] text-coral uppercase">
                In this story
              </p>
              <dl className="mt-4 grid gap-4 text-sm">
                <div>
                  <dt className="text-xs font-bold text-muted">Published</dt>
                  <dd className="mt-1 font-semibold text-[#172f4d]">
                    {publishedLabel ?? "UG UTAG"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-bold text-muted">Category</dt>
                  <dd className="mt-1 font-semibold text-[#172f4d]">
                    {category}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-bold text-muted">Reading time</dt>
                  <dd className="mt-1 font-semibold text-[#172f4d]">
                    About {minutes} min
                  </dd>
                </div>
                {article.attachments.length ? (
                  <div>
                    <dt className="text-xs font-bold text-muted">Documents</dt>
                    <dd className="mt-1">
                      <a
                        href="#documents"
                        className="font-semibold text-coral hover:underline"
                      >
                        View {article.attachments.length} file
                        {article.attachments.length === 1 ? "" : "s"}
                      </a>
                    </dd>
                  </div>
                ) : null}
              </dl>
              <Link
                href="/news"
                className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md border border-line bg-panel px-4 py-2.5 text-xs font-extrabold text-[#172f4d] transition hover:border-coral/40 hover:text-coral"
              >
                All news
                <ArrowRight className="size-3.5" />
              </Link>
            </div>
          </aside>
        </div>

        {related.length ? (
          <section className="mt-16 border-t border-line pt-12 lg:mt-20">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[.68rem] font-extrabold tracking-[.14em] text-coral uppercase">
                  Keep reading
                </p>
                <h2 className="mt-2 text-2xl font-black tracking-tight text-[#172f4d]">
                  More from News
                </h2>
              </div>
              <Link
                href="/news"
                className="inline-flex items-center gap-2 text-xs font-extrabold text-coral hover:text-[#172f4d]"
              >
                Browse all
                <ArrowRight className="size-3.5" />
              </Link>
            </div>
            <div className="mt-8 grid gap-5 md:grid-cols-3">
              {related.map((item, index) => (
                <Link
                  key={item.id}
                  href={`/news/${item.slug}`}
                  className="group flex flex-col overflow-hidden rounded-md border border-line bg-white shadow-[0_8px_26px_rgb(23_43_69_/_8%)] transition hover:border-coral/30"
                >
                  <MediaCover
                    assetId={item.featured_media_id}
                    fallbackSrc={`/brand/${["hero-meeting.jpg", "campus-main.jpg", "hero-leadership.jpg"][index % 3]}`}
                    alt=""
                    className="h-40"
                    variant="w480"
                  >
                    <div className="absolute inset-0 bg-[#102a48]/15" />
                  </MediaCover>
                  <div className="flex flex-1 flex-col p-5">
                    <p className="text-[.65rem] font-extrabold tracking-wide text-coral uppercase">
                      {item.tags[0] ?? "UG UTAG news"}
                    </p>
                    <h3 className="mt-2 text-base font-extrabold leading-snug text-[#172f4d] group-hover:text-coral">
                      {item.title}
                    </h3>
                    {item.published_at ? (
                      <time
                        className="mt-auto pt-4 text-xs font-bold text-muted"
                        dateTime={item.published_at}
                      >
                        {format(new Date(item.published_at), "d MMM yyyy")}
                      </time>
                    ) : null}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </PublicShell>
  );
}
