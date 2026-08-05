"use client";

import { useQuery } from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";
import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarDays,
  FileText,
  MessageSquareText,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import Link from "next/link";

import { PulseChart } from "@/components/dashboard/pulse-chart";
import { WorkspaceRichTextValue } from "@/components/dashboard/workspace-rich-text-value";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatNumber, humanize } from "@/lib/utils";

type Metric = {
  key: string;
  label: string;
  value: number | string;
  change: number | null;
  trend: "up" | "down" | "flat";
};
type Event = {
  id: string;
  title: string;
  start_date: string;
  venue: string | null;
  registrations: number;
  registered: boolean;
};
type Notice = {
  id: string;
  title: string;
  priority: string;
  created_at: string;
  read_at: string | null;
};
type Activity = {
  id: string;
  action: string;
  actor_name: string;
  resource_type: string;
  created_at: string;
};
type Appointment = {
  id: string;
  position: string;
  biography_html: string;
  social_links: Record<string, string>;
};
type Overview = {
  generated_at: string;
  metrics: Metric[];
  pulse: { at: string; engagement: number; events: number; publications: number }[];
  upcoming_events: Event[];
  recent_notifications: Notice[];
  recent_activity: Activity[];
  sections: string[];
  executive_appointment: Appointment | null;
};

const iconMap = {
  members: Users,
  documents: FileText,
  events: CalendarDays,
  unread: MessageSquareText,
};

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "morning";
  return hour < 18 ? "afternoon" : "evening";
}

export function DashboardHome() {
  const query = useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: () => api<Overview>("/api/v1/dashboard/overview"),
    refetchInterval: 120_000,
  });

  if (query.isLoading)
    return (
      <div className="grid animate-pulse gap-5">
        <div className="h-24 rounded-2xl bg-ink/5" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-32 rounded-2xl bg-ink/5" />
          ))}
        </div>
        <div className="h-80 rounded-2xl bg-ink/5" />
      </div>
    );

  if (!query.data)
    return (
      <Card>
        <CardContent className="py-14 text-center">
          <p className="font-black">Dashboard data is temporarily unavailable.</p>
          <button className="mt-4 text-sm text-coral" onClick={() => query.refetch()}>
            Try again
          </button>
        </CardContent>
      </Card>
    );

  const data = query.data;
  // The API returns only the blocks this member is authorized to see.
  const showPulse = data.sections.includes("pulse");
  const showActivity = data.sections.includes("activity");
  const appointment = data.executive_appointment;

  const pulseCard = (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <p className="eyebrow text-coral">Association pulse</p>
            <h3 className="mt-2 text-lg font-black">Engagement over 14 days</h3>
          </div>
          <span className="text-[.65rem] text-muted">Live audit stream</span>
        </div>
      </CardHeader>
      <CardContent>
        <PulseChart data={data.pulse} />
      </CardContent>
    </Card>
  );

  const eventsCard = (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <p className="eyebrow text-coral">Next up</p>
            <h3 className="mt-2 text-lg font-black">Upcoming events</h3>
          </div>
          <Link href="/dashboard/events" className="text-xs font-bold text-coral">
            View all
          </Link>
        </div>
      </CardHeader>
      <CardContent className="divide-y divide-line">
        {data.upcoming_events.length ? (
          data.upcoming_events.map((event) => (
            <Link
              key={event.id}
              href="/dashboard/events"
              className="grid grid-cols-[2.8rem_1fr_auto] items-center gap-3 py-4 first:pt-1"
            >
              <span className="grid size-11 place-items-center rounded-xl bg-ink/5 text-center">
                <span>
                  <b className="block text-sm leading-none">
                    {format(new Date(event.start_date), "dd")}
                  </b>
                  <small className="text-[.5rem] font-bold text-coral uppercase">
                    {format(new Date(event.start_date), "MMM")}
                  </small>
                </span>
              </span>
              <span className="min-w-0">
                <b className="block truncate text-xs">{event.title}</b>
                <small className="mt-1 block truncate text-[.62rem] text-muted">
                  {event.venue ?? "Online"} · {event.registrations} going
                </small>
                {event.registered ? (
                  <small className="mt-1 block text-[.62rem] font-bold text-coral">
                    You are registered
                  </small>
                ) : null}
              </span>
              <ArrowRight className="size-3.5 text-muted" />
            </Link>
          ))
        ) : (
          <p className="py-12 text-center text-xs text-muted">No upcoming events</p>
        )}
      </CardContent>
    </Card>
  );

  const activityCard = (
    <Card>
      <CardHeader>
        <p className="eyebrow text-coral">Activity ledger</p>
        <h3 className="mt-2 text-lg font-black">Recent association changes</h3>
      </CardHeader>
      <CardContent className="divide-y divide-line">
        {data.recent_activity.slice(0, 7).map((item) => (
          <div key={item.id} className="flex items-start gap-3 py-3.5">
            <span className="mt-1.5 size-2 shrink-0 rounded-full bg-gold" />
            <div className="min-w-0">
              <p className="truncate text-xs">
                <b>{item.actor_name}</b> · {humanize(item.action)}
              </p>
              <p className="mt-1 text-[.62rem] text-muted">
                {humanize(item.resource_type)} ·{" "}
                {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
              </p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );

  const notificationsCard = (
    <Card>
      <CardHeader>
        <div className="flex justify-between">
          <div>
            <p className="eyebrow text-coral">Your inbox</p>
            <h3 className="mt-2 text-lg font-black">Recent notifications</h3>
          </div>
          <Link href="/dashboard/notifications" className="text-xs font-bold text-coral">
            Open inbox
          </Link>
        </div>
      </CardHeader>
      <CardContent className="divide-y divide-line">
        {data.recent_notifications.length ? (
          data.recent_notifications.slice(0, 7).map((item) => (
            <Link
              href="/dashboard/notifications"
              key={item.id}
              className="flex items-start gap-3 py-3.5"
            >
              <span
                className={`mt-1 size-2 shrink-0 rounded-full ${item.read_at ? "bg-line" : "bg-coral"}`}
              />
              <div>
                <p className="text-xs font-bold">{item.title}</p>
                <p className="mt-1 text-[.62rem] text-muted">
                  {humanize(item.priority)} ·{" "}
                  {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
                </p>
              </div>
            </Link>
          ))
        ) : (
          <p className="py-12 text-center text-xs text-muted">No notifications yet</p>
        )}
      </CardContent>
    </Card>
  );

  const appointmentCard = appointment ? (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <p className="eyebrow text-coral">Your appointment</p>
            <h3 className="mt-2 text-lg font-black">{humanize(appointment.position)}</h3>
          </div>
          <Link href="/dashboard/profile" className="text-xs font-bold text-coral">
            Edit public profile
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        <span className="inline-flex items-center gap-2 rounded-full bg-ink/5 px-3 py-1.5 text-[.62rem] font-bold">
          <BriefcaseBusiness className="size-3.5 text-coral" /> Published on the public
          leadership page
        </span>
        <div className="mt-4">
          <WorkspaceRichTextValue html={appointment.biography_html} />
        </div>
      </CardContent>
    </Card>
  ) : null;

  return (
    <div className="grid gap-5">
      <section className="relative overflow-hidden rounded-[1.5rem] bg-[#0d1b31] px-6 py-7 text-white sm:px-8">
        <div className="absolute inset-0 hairline-grid opacity-10" />
        <div className="relative flex flex-col justify-between gap-7 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow text-gold">
              {showPulse ? "Association intelligence" : "Your workspace"}
            </p>
            <h2 className="display-type mt-4 text-4xl sm:text-5xl">Good {greeting()}.</h2>
            <p className="mt-3 text-sm text-white/55">
              {showPulse
                ? "Here is what is moving across UG UTAG right now."
                : "Here are the events, documents, and updates that concern you."}
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-[.67rem] text-white/55">
            <Sparkles className="size-3.5 text-gold" /> Refreshed{" "}
            {formatDistanceToNow(new Date(data.generated_at), { addSuffix: true })}
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {data.metrics.map((metric) => {
          const Icon = iconMap[metric.key as keyof typeof iconMap] ?? Sparkles;
          return (
            <Card key={metric.key} className="min-w-0">
              <CardContent className="p-4 sm:p-5">
                <div className="flex items-start justify-between gap-3">
                  <span className="grid size-9 place-items-center rounded-xl bg-ink/5">
                    <Icon className="size-4 text-coral" />
                  </span>
                  {metric.change != null && (
                    <span
                      className={`inline-flex items-center gap-1 text-[.62rem] font-bold ${metric.trend === "down" ? "text-red-600" : "text-emerald-600"}`}
                    >
                      {metric.trend === "down" ? (
                        <TrendingDown className="size-3" />
                      ) : (
                        <TrendingUp className="size-3" />
                      )}
                      {Math.abs(metric.change)}%
                    </span>
                  )}
                </div>
                <strong className="mt-6 block text-2xl font-black sm:text-3xl">
                  {typeof metric.value === "number" ? formatNumber(metric.value) : metric.value}
                </strong>
                <span className="mt-1 block truncate text-[.65rem] text-muted sm:text-xs">
                  {metric.label}
                </span>
              </CardContent>
            </Card>
          );
        })}
      </section>

      {showPulse ? (
        <>
          <section className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
            {pulseCard}
            {eventsCard}
          </section>
          <section className={showActivity ? "grid gap-5 xl:grid-cols-2" : "grid gap-5"}>
            {showActivity ? activityCard : null}
            {notificationsCard}
          </section>
        </>
      ) : (
        <section className="grid gap-5 xl:grid-cols-2">
          {eventsCard}
          {notificationsCard}
        </section>
      )}

      {appointmentCard}
    </div>
  );
}
