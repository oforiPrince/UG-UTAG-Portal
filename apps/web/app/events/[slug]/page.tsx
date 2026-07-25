import { format } from "date-fns";
import {
  ArrowDownToLine,
  CalendarDays,
  Camera,
  Clock3,
  ExternalLink,
  FileText,
  Mail,
  MapPin,
  Phone,
  Users,
} from "lucide-react";
import { notFound } from "next/navigation";

import { PublicShell } from "@/components/public/public-shell";
import { Button } from "@/components/ui/button";
import { publicApi } from "@/lib/api";

type EventSpeaker = {
  name?: string;
  title?: string;
  bio?: string;
  presentation_title?: string;
};

type EventScheduleItem = {
  date?: string;
  start_time?: string;
  end_time?: string;
  title?: string;
  location?: string;
  description?: string;
};

type Event = {
  slug: string;
  title: string;
  short_description: string;
  description_html: string;
  start_date: string;
  start_time: string | null;
  end_date: string | null;
  venue: string | null;
  is_online: boolean;
  event_type: string;
  registration_required: boolean;
  registration_url: string | null;
  registrations: number;
  featured_media_id: string | null;
  photos_url: string | null;
  organizer?: { name?: string; email?: string; phone?: string } | null;
  speakers?: EventSpeaker[] | null;
  schedule?: EventScheduleItem[] | null;
  attachments?: {
    media_asset_id: string;
    filename: string;
    content_type: string;
    content_url: string;
  }[] | null;
};

function scheduleTime(item: EventScheduleItem) {
  const start = item.start_time?.slice(0, 5);
  const end = item.end_time?.slice(0, 5);
  if (start && end) return `${start}–${end}`;
  return start ?? null;
}

export default async function EventPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const event = await publicApi<Event | null>(
    `/api/v1/public/events/${encodeURIComponent(slug)}`,
    null,
    { revalidate: false },
  );
  if (!event) notFound();
  const speakers = event.speakers ?? [];
  const schedule = event.schedule ?? [];
  const attachments = event.attachments ?? [];
  const organizer = event.organizer ?? {};
  return (
    <PublicShell>
      <header className="relative isolate overflow-hidden bg-[#122b48] text-white">
        <div
          className="absolute inset-0 -z-20 bg-cover bg-center"
          style={{
            backgroundImage: `url('${
              event.featured_media_id
                ? `/api/v1/public/media/${event.featured_media_id}`
                : "/brand/hero-leadership.jpg"
            }')`,
          }}
        />
        <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(13,41,71,.95),rgba(13,41,71,.72))]" />
        <div className="mx-auto max-w-[82rem] px-5 py-14 sm:px-6 sm:py-18 lg:px-8 lg:py-20">
          <p className="text-[.7rem] font-extrabold tracking-[.14em] text-gold uppercase">
            {event.event_type}
          </p>
          <h1 className="display-type mt-4 max-w-5xl text-4xl leading-tight text-white sm:text-5xl lg:text-6xl">
            {event.title}
          </h1>
          <p className="mt-5 max-w-3xl text-base leading-8 text-white/76">
            {event.short_description}
          </p>
        </div>
        <div className="h-1 bg-gold" />
      </header>
      <section className="mx-auto grid max-w-[82rem] gap-10 px-5 py-14 sm:px-6 lg:grid-cols-[1fr_21rem] lg:px-8 lg:py-18">
        <div>
          <div
            className="prose prose-lg max-w-none text-ink prose-headings:text-[#172f4d] prose-headings:font-bold prose-a:text-coral"
            dangerouslySetInnerHTML={{ __html: event.description_html }}
          />
          {speakers.length ? (
            <section className="mt-12 border-t border-line pt-8">
              <h2 className="text-xl font-black text-[#172f4d]">Speakers</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {speakers.map((speaker, index) => (
                  <article
                    key={`${speaker.name ?? "speaker"}-${index}`}
                    className="rounded-md border border-line bg-panel p-5"
                  >
                    <h3 className="text-base font-extrabold text-[#172f4d]">
                      {speaker.name}
                    </h3>
                    {speaker.title ? (
                      <p className="mt-1 text-sm font-semibold text-coral">
                        {speaker.title}
                      </p>
                    ) : null}
                    {speaker.presentation_title ? (
                      <p className="mt-3 text-sm font-bold text-ink">
                        “{speaker.presentation_title}”
                      </p>
                    ) : null}
                    {speaker.bio ? (
                      <p className="mt-3 text-sm leading-7 text-ink/75">
                        {speaker.bio}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}
          {schedule.length ? (
            <section className="mt-12 border-t border-line pt-8">
              <h2 className="text-xl font-black text-[#172f4d]">
                Event schedule
              </h2>
              <ol className="mt-4 grid gap-4">
                {schedule.map((item, index) => (
                  <li
                    key={`${item.title ?? "session"}-${index}`}
                    className="rounded-md border border-line bg-panel p-5"
                  >
                    <p className="text-[.7rem] font-extrabold tracking-[.12em] text-coral uppercase">
                      {[
                        item.date
                          ? format(new Date(item.date), "EEEE, d MMMM yyyy")
                          : null,
                        scheduleTime(item),
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    <h3 className="mt-2 text-base font-extrabold text-[#172f4d]">
                      {item.title}
                    </h3>
                    {item.location ? (
                      <p className="mt-1 flex items-center gap-2 text-sm text-ink/75">
                        <MapPin className="size-4 shrink-0 text-gold" />
                        {item.location}
                      </p>
                    ) : null}
                    {item.description ? (
                      <p className="mt-2 text-sm leading-7 text-ink/75">
                        {item.description}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
          {attachments.length ? (
            <section className="mt-12 border-t border-line pt-8">
              <h2 className="text-xl font-black text-[#172f4d]">
                Event files and images
              </h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {attachments.map((attachment) =>
                  attachment.content_type.startsWith("image/") ? (
                    <a
                      key={attachment.media_asset_id}
                      href={attachment.content_url}
                      target="_blank"
                      rel="noreferrer"
                      className="overflow-hidden rounded-md border border-line bg-panel"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={attachment.content_url}
                        alt={attachment.filename}
                        className="aspect-[4/3] w-full object-cover"
                      />
                      <b className="block truncate p-3 text-sm">
                        {attachment.filename}
                      </b>
                    </a>
                  ) : (
                    <a
                      key={attachment.media_asset_id}
                      href={attachment.content_url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-3 rounded-md border border-line bg-panel p-4"
                    >
                      <FileText className="size-5 shrink-0 text-coral" />
                      <b className="min-w-0 flex-1 truncate text-sm">
                        {attachment.filename}
                      </b>
                      <ArrowDownToLine className="size-4 text-coral" />
                    </a>
                  ),
                )}
              </div>
            </section>
          ) : null}
        </div>
        <aside className="h-fit rounded-md border border-line bg-panel p-6 shadow-[0_10px_30px_rgb(23_43_69_/_8%)]">
          <h2 className="text-lg font-extrabold text-[#172f4d]">
            Event details
          </h2>
          <div className="mt-5 grid gap-5 border-t border-line pt-5 text-sm">
            <p className="flex items-start gap-3">
              <CalendarDays className="mt-0.5 size-5 shrink-0 text-gold" />
              {format(new Date(event.start_date), "EEEE, d MMMM yyyy")}
            </p>
            {event.start_time && (
              <p className="flex items-start gap-3">
                <Clock3 className="mt-0.5 size-5 shrink-0 text-gold" />
                {event.start_time.slice(0, 5)}
              </p>
            )}
            <p className="flex items-start gap-3">
              <MapPin className="mt-0.5 size-5 shrink-0 text-gold" />
              {event.is_online ? "Online" : event.venue}
            </p>
            <p className="flex items-start gap-3">
              <Users className="mt-0.5 size-5 shrink-0 text-gold" />
              {event.registrations} registrations
            </p>
          </div>
          {organizer.name || organizer.email || organizer.phone ? (
            <div className="mt-6 border-t border-line pt-5">
              <h3 className="text-sm font-extrabold text-[#172f4d]">
                Organizer
              </h3>
              <div className="mt-3 grid gap-3 text-sm">
                {organizer.name ? (
                  <p className="flex items-start gap-3">
                    <Users className="mt-0.5 size-4 shrink-0 text-gold" />
                    {organizer.name}
                  </p>
                ) : null}
                {organizer.email ? (
                  <a
                    className="flex items-start gap-3 break-all hover:text-coral"
                    href={`mailto:${organizer.email}`}
                  >
                    <Mail className="mt-0.5 size-4 shrink-0 text-gold" />
                    {organizer.email}
                  </a>
                ) : null}
                {organizer.phone ? (
                  <a
                    className="flex items-start gap-3 hover:text-coral"
                    href={`tel:${organizer.phone}`}
                  >
                    <Phone className="mt-0.5 size-4 shrink-0 text-gold" />
                    {organizer.phone}
                  </a>
                ) : null}
              </div>
            </div>
          ) : null}
          {event.registration_url ? (
            <Button className="mt-7 w-full rounded-md" asChild>
              <a href={event.registration_url} target="_blank" rel="noreferrer">
                <ExternalLink className="size-4" /> Register for this event
              </a>
            </Button>
          ) : event.registration_required ? (
            <Button className="mt-7 w-full rounded-md" asChild>
              <a href="/login">Sign in to register</a>
            </Button>
          ) : null}
          {event.photos_url ? (
            <Button
              className="mt-3 w-full rounded-md"
              variant="outline"
              asChild
            >
              <a href={event.photos_url} target="_blank" rel="noreferrer">
                <Camera className="size-4" /> View event photos
              </a>
            </Button>
          ) : null}
        </aside>
      </section>
    </PublicShell>
  );
}
