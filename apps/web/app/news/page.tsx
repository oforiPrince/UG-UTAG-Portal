import { format } from "date-fns";
import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageHero } from "@/components/public/page-hero";
import { PublicEmptyState } from "@/components/public/public-empty-state";
import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";

export const metadata: Metadata = { title: "News & statements" };
type Article = {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  tags: string[];
  published_at: string | null;
  featured_media_id: string | null;
};
type Page<T> = { items: T[]; total: number };
const fallback: Page<Article> = { total: 0, items: [] };

export default async function NewsPage() {
  const data = await publicApi<Page<Article>>(
    "/api/v1/public/articles?page_size=24",
    fallback,
    { revalidate: false },
  );
  const images = ["hero-meeting.jpg", "campus-main.jpg", "hero-leadership.jpg"];
  return (
    <PublicShell>
      <PageHero
        eyebrow="News"
        title="News, statements and member updates"
        intro="Official statements, association briefings and stories from across the University of Ghana academic community."
      />
      <section className="mx-auto max-w-[82rem] px-5 py-16 sm:px-6 lg:px-8 lg:py-22">
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {data.items.length === 0 && (
            <PublicEmptyState
              title="No public news has been published"
              description="Official statements and association updates will appear here when they are released."
            />
          )}
          {data.items.map((article, index) => (
            <Link
              href={`/news/${article.slug}`}
              key={article.id}
              className="group flex flex-col overflow-hidden rounded-md border border-line bg-white shadow-[0_8px_26px_rgb(23_43_69_/_8%)]"
            >
              <div
                className="relative h-52 bg-cover bg-center"
                style={{
                  backgroundImage: `url('${
                    article.featured_media_id
                      ? `/api/v1/public/media/${article.featured_media_id}`
                      : `/brand/${images[index % images.length]}`
                  }')`,
                }}
              >
                <div className="absolute inset-0 bg-[#102a48]/20" />
                {article.published_at && (
                  <time
                    className="absolute bottom-0 left-5 bg-gold px-3 py-2 text-xs font-black text-[#172f4d]"
                    dateTime={article.published_at}
                  >
                    {format(new Date(article.published_at), "dd MMM yyyy")}
                  </time>
                )}
              </div>
              <div className="flex flex-1 flex-col p-6">
                <p className="text-[.68rem] font-extrabold tracking-wide text-coral uppercase">
                  {article.tags[0] ?? "UG UTAG news"}
                </p>
                <h2 className="mt-3 text-xl font-extrabold leading-snug text-[#172f4d] group-hover:text-coral">
                  {article.title}
                </h2>
                <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted">
                  {article.excerpt}
                </p>
                <span className="mt-auto inline-flex items-center gap-2 pt-6 text-xs font-extrabold text-coral">
                  Read more{" "}
                  <ArrowRight className="size-4 transition group-hover:translate-x-1" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </PublicShell>
  );
}
