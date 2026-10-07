import { format } from "date-fns";
import {
  ArrowRight,
  BookOpenCheck,
  CalendarDays,
  FlaskConical,
  GraduationCap,
  HandHeart,
  HeartHandshake,
  Landmark,
  MapPin,
  Megaphone,
  MessageCircleMore,
  Scale,
  TrendingUp,
  UsersRound,
} from "lucide-react";
import Link from "next/link";

import { ExecutiveCard } from "@/components/public/executive-card";
import {
  HomeHero,
  type HomeCarouselSlide,
} from "@/components/public/home-hero";
import { AdSlotBanner } from "@/components/public/ad-slot-banner";
import { MediaCover } from "@/components/public/media-cover";
import { PublicShell } from "@/components/public/public-shell";
import { Button } from "@/components/ui/button";
import { publicApi } from "@/lib/api";
import {
  executiveOfficers,
  type PublicExecutiveProfile,
} from "@/lib/leadership";

export const dynamic = "force-dynamic";

type Article = {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  tags: string[];
  published_at: string | null;
  featured_media_id: string | null;
};
type Event = {
  id: string;
  slug: string;
  title: string;
  short_description: string;
  start_date: string;
  event_type: string;
  venue: string | null;
  featured_media_id: string | null;
};
type HomeData = {
  settings: Record<string, Record<string, unknown>>;
  featured_articles: Article[];
  upcoming_events: Event[];
  leadership: PublicExecutiveProfile[];
};
type Gallery = {
  id: string;
  slug: string;
  title: string;
  images: {
    id: string;
    url: string;
    alt_text: string | null;
    caption: string | null;
  }[];
};

const fallback: HomeData = {
  settings: {},
  featured_articles: [],
  upcoming_events: [],
  leadership: [],
};

const pillars = [
  [
    GraduationCap,
    "Quality Education",
    "Defending academic freedom and the conditions that allow teaching and scholarship to thrive.",
  ],
  [
    FlaskConical,
    "Teaching & Research",
    "Advancing standards, resources, and opportunities for excellent teaching and impactful research.",
  ],
  [
    Megaphone,
    "Member Advocacy",
    "Representing member concerns to University Management, UTAG National, and public authorities.",
  ],
  [
    HeartHandshake,
    "Member Welfare",
    "Promoting fair conditions of service, professional wellbeing, and a supportive academic community.",
  ],
] as const;

const aims = [
  [
    HandHeart,
    "Promote Welfare",
    "Seek continuous improvement in the working conditions, facilities, and professional wellbeing of University teachers.",
  ],
  [
    UsersRound,
    "Foster Unity",
    "Build common purpose, mutual support, and meaningful participation across rank, discipline, and college.",
  ],
  [
    MessageCircleMore,
    "Improve Communication",
    "Strengthen dialogue among members, University leadership, and stakeholders beyond the campus.",
  ],
  [
    TrendingUp,
    "Advance Academics",
    "Support excellent teaching, research, mentorship, and public service across the University.",
  ],
  [
    Landmark,
    "Serve the Institution",
    "Contribute constructively to a strong, accountable, and globally respected University of Ghana.",
  ],
  [
    Scale,
    "Uphold Academic Freedom",
    "Protect open inquiry, professional responsibility, and the freedom required for scholarship.",
  ],
] as const;

function SectionHeading({
  kicker,
  title,
  copy,
  inverse = false,
}: {
  kicker: string;
  title: string;
  copy?: string;
  inverse?: boolean;
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <p className="text-[.72rem] font-extrabold tracking-[.15em] text-coral uppercase">
        {kicker}
      </p>
      <h2
        className={`display-type mt-3 text-3xl leading-tight sm:text-4xl ${inverse ? "text-white" : "text-[#172f4d]"}`}
      >
        {title}
      </h2>
      {copy && (
        <p
          className={`mx-auto mt-4 max-w-2xl text-sm leading-7 sm:text-base ${inverse ? "text-white/68" : "text-muted"}`}
        >
          {copy}
        </p>
      )}
      <div className="mx-auto mt-5 flex w-24 items-center gap-2">
        <span className="h-px flex-1 bg-gold" />
        <BookOpenCheck className="size-4 text-gold" />
        <span className="h-px flex-1 bg-gold" />
      </div>
    </div>
  );
}

export default async function Home() {
  const [data, galleries] = await Promise.all([
    publicApi<HomeData>("/api/v1/public/home", fallback, {
      revalidate: false,
    }),
    publicApi<Gallery[]>("/api/v1/public/galleries", []),
  ]);
  const leadership = executiveOfficers(data.leadership);
  const galleryHighlights = galleries
    .flatMap((gallery) =>
      gallery.images.map((image) => ({
        ...image,
        gallerySlug: gallery.slug,
        galleryTitle: gallery.title,
      })),
    )
    .slice(0, 3);
  const home = (data.settings["site.home"] ?? {}) as {
    eyebrow?: string;
    headline?: string;
    introduction?: string;
  };
  const carousel = (data.settings["site.carousel"] ?? {}) as {
    slides?: HomeCarouselSlide[];
  };

  return (
    <PublicShell>
      <HomeHero
        eyebrow={home.eyebrow}
        headline={home.headline}
        introduction={home.introduction}
        slides={carousel.slides ?? []}
      />

      <AdSlotBanner
        slotKey="home-after-hero"
        context="home"
        priority
      />

      <section
        aria-label="Our core commitments"
        className="border-b border-line bg-white"
      >
        <div className="mx-auto grid max-w-[82rem] sm:grid-cols-2 lg:grid-cols-4">
          {pillars.map(([Icon, title, copy]) => (
            <article
              key={title}
              className="group border-b border-line px-6 py-9 text-center sm:border-r lg:border-b-0 lg:px-7 lg:py-11"
            >
              <span className="mx-auto grid size-16 place-items-center rounded-full border border-[#b9cadb] bg-[#f4f7fb] text-coral transition group-hover:border-[#172f4d] group-hover:bg-[#172f4d] group-hover:text-white">
                <Icon className="size-7" />
              </span>
              <h2 className="mt-5 text-base font-extrabold text-[#172f4d]">
                {title}
              </h2>
              <p className="mt-3 text-sm leading-6 text-muted">{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto grid max-w-[82rem] gap-10 px-5 py-18 sm:px-6 lg:grid-cols-2 lg:items-center lg:gap-16 lg:px-8 lg:py-24">
        <div>
          <p className="text-[.72rem] font-extrabold tracking-[.15em] text-coral uppercase">
            Welcome to UG UTAG
          </p>
          <h2 className="display-type mt-4 text-3xl leading-tight text-[#172f4d] sm:text-4xl">
            A united voice for University of Ghana academics
          </h2>
          <div className="mt-5 h-1 w-16 bg-gold" />
          <p className="mt-6 text-sm leading-7 text-muted sm:text-base">
            The University of Ghana Branch of the University Teachers
            Association of Ghana represents teaching and research staff and
            champions their academic, professional, and economic welfare.
          </p>
          <p className="mt-4 text-sm leading-7 text-muted sm:text-base">
            We engage University Management, National Leadership of UTAG, and institutions of state
            to promote fair conditions of service, protect academic
            freedom, and strengthen the resources required for teaching, research,
            and community service.
          </p>
          <Button asChild className="mt-7 rounded-md">
            <Link href="/about">
              Know more about us <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
        <div className="relative overflow-hidden rounded-md border border-line bg-panel p-2 shadow-[0_18px_45px_rgb(23_43_69_/_14%)]">
          <div
            className="aspect-[16/9] bg-cover bg-center"
            style={{ backgroundImage: "url('/brand/campus-gate.png')" }}
            role="img"
            aria-label="University of Ghana campus entrance"
          />
          <div className="absolute right-0 bottom-0 border-t-4 border-gold bg-[#172f4d] px-5 py-3 text-xs font-bold text-white">
            University of Ghana · Legon
          </div>
        </div>
      </section>

      {data.upcoming_events.length > 0 ? (
        <section className="bg-[#f5f8fb] px-5 py-18 sm:px-6 lg:px-8 lg:py-24">
          <div className="mx-auto max-w-[82rem]">
            <SectionHeading
              kicker="Our events"
              title="Meet, learn, and shape our common work"
              copy="Upcoming meetings and activities for members and the wider academic community."
            />
            <div className="mt-10 grid gap-6 lg:grid-cols-3">
              {data.upcoming_events.slice(0, 3).map((event, index) => (
                <Link
                  key={event.id}
                  href={`/events/${event.slug}`}
                  className="group overflow-hidden rounded-md border border-line bg-white shadow-[0_8px_24px_rgb(23_43_69_/_7%)]"
                >
                  <MediaCover
                    assetId={event.featured_media_id}
                    fallbackSrc={`/brand/${index % 2 === 0 ? "hero-leadership.jpg" : "hero-meeting.jpg"}`}
                    alt=""
                    className="h-44"
                    variant="w480"
                  >
                    <div className="absolute inset-0 bg-[#102a48]/25" />
                    <time
                      className="absolute bottom-0 left-5 grid min-w-16 bg-gold px-3 py-2 text-center text-[#172f4d]"
                      dateTime={event.start_date}
                    >
                      <span className="text-xl font-black leading-none">
                        {format(new Date(event.start_date), "dd")}
                      </span>
                      <span className="mt-1 text-[.62rem] font-extrabold tracking-wide uppercase">
                        {format(new Date(event.start_date), "MMM yyyy")}
                      </span>
                    </time>
                  </MediaCover>
                  <div className="p-6">
                    <p className="text-[.68rem] font-bold tracking-wide text-coral uppercase">
                      {event.event_type}
                    </p>
                    <h3 className="mt-2 text-xl font-extrabold text-[#172f4d] group-hover:text-coral">
                      {event.title}
                    </h3>
                    <p className="mt-3 line-clamp-2 text-sm leading-6 text-muted">
                      {event.short_description}
                    </p>
                    <p className="mt-5 flex items-center gap-2 border-t border-line pt-4 text-xs font-bold text-muted">
                      <MapPin className="size-4 text-gold" />{" "}
                      {event.venue ?? "Online"}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
            <div className="mt-9 text-center">
              <Button asChild className="rounded-md" variant="outline">
                <Link href="/events">
                  View all events <CalendarDays className="size-4" />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      {galleryHighlights.length > 0 ? (
        <section className="px-5 py-18 sm:px-6 lg:px-8 lg:py-24">
          <div className="mx-auto max-w-[82rem]">
            <SectionHeading
              kicker="Our gallery"
              title="UG UTAG in action"
              copy="A visual record of engagement, leadership, and academic community life."
            />
            <div className="mt-10 grid gap-3 md:grid-cols-[1.25fr_.75fr]">
              <Link
                href={`/gallery/${galleryHighlights[0].gallerySlug}`}
                className="group relative min-h-72 overflow-hidden rounded-md md:min-h-[26rem]"
                aria-label={
                  galleryHighlights[0].alt_text ??
                  galleryHighlights[0].galleryTitle
                }
              >
                <MediaCover
                  assetId={galleryHighlights[0].id}
                  alt={
                    galleryHighlights[0].alt_text ??
                    galleryHighlights[0].galleryTitle
                  }
                  className="absolute inset-0"
                  variant="w960"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#0b2744]/85 via-transparent to-transparent" />
                <div className="absolute right-0 bottom-0 left-0 p-6 text-white">
                  <p className="text-[.68rem] font-bold tracking-widest text-gold uppercase">
                    Moderated gallery
                  </p>
                  <h3 className="mt-2 text-2xl font-extrabold">
                    {galleryHighlights[0].caption ??
                      galleryHighlights[0].galleryTitle}
                  </h3>
                </div>
              </Link>
              <div className="grid gap-3">
                {galleryHighlights.slice(1).map((image) => (
                  <Link
                    key={image.id}
                    href={`/gallery/${image.gallerySlug}`}
                    className="group relative min-h-48 overflow-hidden rounded-md"
                    aria-label={image.alt_text ?? image.galleryTitle}
                  >
                    <MediaCover
                      assetId={image.id}
                      alt={image.alt_text ?? image.galleryTitle}
                      className="absolute inset-0"
                      variant="w480"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0b2744]/80 via-transparent to-transparent" />
                    <span className="absolute right-5 bottom-4 left-5 font-extrabold text-white">
                      {image.caption ?? image.galleryTitle}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {leadership.length > 0 ? (
        <section className="bg-[#172f4d] px-5 py-18 text-white sm:px-6 lg:px-8 lg:py-24">
          <div className="mx-auto max-w-[82rem]">
            <SectionHeading
              kicker="Executive officers"
              title="Leadership in service to members"
              copy="Meet the officers entrusted with leading the University of Ghana Branch of UTAG."
              inverse
            />
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
              {leadership.map((leader) => (
                <ExecutiveCard compact key={leader.id} profile={leader} />
              ))}
            </div>
            <div className="mt-9 text-center">
              <Button
                asChild
                className="rounded-md border-white/30 bg-transparent text-white hover:bg-white/10"
                variant="outline"
              >
                <Link href="/leadership">
                  Meet the executive <ArrowRight className="size-4" />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      <section className="bg-[#f5f8fb] px-5 py-18 sm:px-6 lg:px-8 lg:py-24">
        <div className="mx-auto max-w-[82rem]">
          <SectionHeading
            kicker="Our aims"
            title="What guides our work"
            copy="A clear commitment to member welfare, academic progress, and a strong University community."
          />
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {aims.map(([Icon, title, copy]) => (
              <article
                key={title}
                className="rounded-md border border-line bg-white p-6 transition hover:-translate-y-1 hover:border-[#b8c9da] hover:shadow-lg"
              >
                <span className="grid size-12 place-items-center rounded-full bg-[#172f4d] text-gold">
                  <Icon className="size-5" />
                </span>
                <h3 className="mt-5 text-lg font-extrabold text-[#172f4d]">
                  {title}
                </h3>
                <p className="mt-3 text-sm leading-6 text-muted">{copy}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {data.featured_articles.length > 0 ? (
        <section className="px-5 py-18 sm:px-6 lg:px-8 lg:py-24">
          <div className="mx-auto max-w-[82rem]">
            <SectionHeading
              kicker="Our news"
              title="Latest from UG UTAG"
              copy="Official updates, statements, and stories from the Association."
            />
            <div className="mt-10 grid gap-6 lg:grid-cols-3">
              {data.featured_articles.slice(0, 3).map((article, index) => (
                <Link
                  key={article.id}
                  href={`/news/${article.slug}`}
                  className="group flex flex-col overflow-hidden rounded-md border border-line bg-white shadow-[0_8px_24px_rgb(23_43_69_/_7%)]"
                >
                  <MediaCover
                    assetId={article.featured_media_id}
                    fallbackSrc={`/brand/${index === 1 ? "campus-main.jpg" : index === 2 ? "hero-leadership.jpg" : "hero-meeting.jpg"}`}
                    alt=""
                    className="h-44"
                    variant="w480"
                  >
                    <div className="absolute inset-0 bg-[#102a48]/22" />
                  </MediaCover>
                  <div className="flex flex-1 flex-col p-6">
                    <p className="text-[.68rem] font-extrabold tracking-wide text-coral uppercase">
                      {article.tags[0] ?? "Association news"}
                    </p>
                    <h3 className="mt-3 text-xl font-extrabold leading-snug text-[#172f4d] group-hover:text-coral">
                      {article.title}
                    </h3>
                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted">
                      {article.excerpt}
                    </p>
                    <div className="mt-auto flex items-center justify-between border-t border-line pt-5 text-xs font-bold text-muted">
                      <span>
                        {article.published_at
                          ? format(
                              new Date(article.published_at),
                              "d MMMM yyyy",
                            )
                          : "Recent"}
                      </span>
                      <ArrowRight className="size-4 text-coral transition group-hover:translate-x-1" />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
            <div className="mt-9 text-center">
              <Button asChild className="rounded-md">
                <Link href="/news">
                  View all news <ArrowRight className="size-4" />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      ) : null}

    </PublicShell>
  );
}
