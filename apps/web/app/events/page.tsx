import { format } from "date-fns";
import { ArrowRight, Clock3, MapPin } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageHero } from "@/components/public/page-hero";
import { AdSlotBanner } from "@/components/public/ad-slot-banner";
import { MediaCover } from "@/components/public/media-cover";
import { PublicEmptyState } from "@/components/public/public-empty-state";
import { PublicShell } from "@/components/public/public-shell";
import { publicApi } from "@/lib/api";

export const metadata: Metadata = { title: "Events" };
type Event = {
  id: string;
  slug: string;
  title: string;
  short_description: string;
  start_date: string;
  end_date: string | null;
  event_type: string;
  venue: string | null;
  is_online: boolean;
  start_time?: string | null;
  featured_media_id: string | null;
};
type Page<T> = { items: T[]; total: number };
const fallback: Page<Event> = { total: 0, items: [] };

export default async function EventsPage() {
  const data = await publicApi<Page<Event>>(
    "/api/v1/public/events?page_size=24",
    fallback,
    { revalidate: false },
  );
  return (
    <PublicShell>
      <PageHero
        eyebrow="Events"
        title="Meetings and activities that bring us together"
        intro="General meetings, forums, workshops and community activities for members and invited guests."
      />
      <section className="mx-auto max-w-[82rem] px-5 py-16 sm:px-6 lg:px-8 lg:py-22">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
          <div className="grid gap-6 md:grid-cols-2">
            {data.items.length === 0 && (
              <PublicEmptyState
                title="No upcoming public events"
                description="Confirmed general meetings, forums and workshops will be listed here."
              />
            )}
            {data.items.map((event, index) => (
              <Link
                key={event.id}
                href={`/events/${event.slug}`}
                className="group overflow-hidden rounded-md border border-line bg-white shadow-[0_8px_26px_rgb(23_43_69_/_8%)]"
              >
                <MediaCover
                  assetId={event.featured_media_id}
                  fallbackSrc={`/brand/${index % 2 === 0 ? "hero-leadership.jpg" : "hero-meeting.jpg"}`}
                  alt=""
                  className="h-52"
                  variant="w480"
                >
                  <div className="absolute inset-0 bg-[#102a48]/22" />
                  <time
                    className="absolute bottom-0 left-5 grid min-w-17 bg-gold px-3 py-2 text-center text-[#172f4d]"
                    dateTime={event.start_date}
                  >
                    <span className="text-2xl font-black leading-none">
                      {format(new Date(event.start_date), "dd")}
                    </span>
                    <span className="mt-1 text-[.62rem] font-extrabold tracking-wide uppercase">
                      {format(new Date(event.start_date), "MMM yyyy")}
                    </span>
                  </time>
                </MediaCover>
                <div className="p-6">
                  <p className="text-[.68rem] font-extrabold tracking-wide text-coral uppercase">
                    {event.event_type}
                  </p>
                  <h2 className="mt-3 text-xl font-extrabold leading-snug text-[#172f4d] group-hover:text-coral">
                    {event.title}
                  </h2>
                  <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted">
                    {event.short_description}
                  </p>
                  <div className="mt-5 grid gap-2 border-t border-line pt-4 text-xs font-semibold text-muted">
                    <span className="flex items-center gap-2">
                      <MapPin className="size-4 text-gold" />
                      {event.is_online ? "Online" : event.venue}
                    </span>
                    {event.start_time && (
                      <span className="flex items-center gap-2">
                        <Clock3 className="size-4 text-gold" />
                        {event.start_time.slice(0, 5)}
                      </span>
                    )}
                  </div>
                  <span className="mt-5 inline-flex items-center gap-2 text-xs font-extrabold text-coral">
                    View event{" "}
                    <ArrowRight className="size-4 transition group-hover:translate-x-1" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
          <AdSlotBanner slotKey="events-sidebar" context="listing-rail" />
        </div>
      </section>
    </PublicShell>
  );
}
