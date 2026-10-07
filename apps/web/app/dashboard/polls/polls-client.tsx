"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  LockKeyhole,
  Plus,
  Search,
  Users,
  Vote,
} from "lucide-react";
import Link from "next/link";
import { useDeferredValue, useState } from "react";

import { useRealtime } from "@/components/realtime-provider";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatPollDate, type Poll, type PollPage } from "@/lib/polls";
import { cn, formatNumber } from "@/lib/utils";

import {
  PollError,
  PollLoading,
  PollStatusBadge,
  usePollBoundaryRefresh,
} from "./poll-ui";

type PollFilter = "all" | "open" | "scheduled" | "closed" | "draft";

function PollListCard({
  poll,
  receivedAt,
}: {
  poll: Poll;
  receivedAt: number;
}) {
  usePollBoundaryRefresh(poll, receivedAt);
  return (
    <Link
      href={`/dashboard/polls/${poll.id}`}
      className="workspace-folio group flex h-full flex-col rounded-[1.5rem] p-6 transition hover:shadow-[0_18px_50px_rgba(12,25,48,.10)] focus-visible:ring-2 focus-visible:ring-gold sm:p-7"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PollStatusBadge status={poll.status} />
        {poll.has_voted ? (
          <span className="inline-flex items-center gap-1.5 text-[.68rem] font-bold text-muted">
            <Check className="size-3.5" /> You voted
          </span>
        ) : null}
      </div>
      <h2 className="display-type mt-5 text-xl leading-snug">{poll.title}</h2>
      <p className="mt-3 line-clamp-3 flex-1 text-sm leading-6 text-muted">
        {poll.question}
      </p>
      <div className="workspace-rule mt-6" />
      <div className="mt-4 grid gap-2 text-[.72rem] text-muted">
        <span className="flex items-center gap-2">
          <Users className="size-3.5" /> {formatNumber(poll.eligible_count)}{" "}
          eligible members
        </span>
        <span className="flex items-center gap-2">
          <CalendarDays className="size-3.5" />{" "}
          {poll.status === "scheduled"
            ? `Opens ${formatPollDate(poll.opens_at)}`
            : poll.closes_at
              ? `${poll.status === "closed" ? "Closed" : "Closes"} ${formatPollDate(poll.status === "closed" ? (poll.closed_at ?? poll.closes_at) : poll.closes_at)}`
              : "Set a voting deadline"}{" "}
          GMT
        </span>
        <span className="flex items-center gap-2">
          <LockKeyhole className="size-3.5" />{" "}
          {poll.privacy === "named" ? "Named ballot" : "Confidential ballot"} ·{" "}
          {poll.kind === "multiple" ? "Multiple choices" : "Single choice"}
        </span>
      </div>
      <div className="mt-6 flex items-center justify-between text-sm font-bold">
        <span>
          {poll.status === "draft"
            ? "Continue draft"
            : poll.can_vote && !poll.has_voted
              ? "Have your say"
              : poll.can_view_results
                ? "View poll & results"
                : "View poll"}
        </span>
        <ArrowRight className="size-4 text-coral transition group-hover:translate-x-1" />
      </div>
    </Link>
  );
}

export function PollsClient() {
  const { state: connection } = useRealtime();
  const [state, setState] = useState<PollFilter>("all");
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const [page, setPage] = useState(1);
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<{ permissions: string[] }>("/api/v1/auth/me"),
    staleTime: 60_000,
  });
  const canManage = user.data?.permissions.includes("polls.manage") ?? false;
  const polls = useQuery({
    queryKey: ["polls", "list", state, q, page],
    queryFn: () =>
      api<PollPage<Poll>>(
        `/api/v1/polls?${new URLSearchParams({ state, q, page: String(page), page_size: "12" })}`,
      ),
    refetchInterval: connection === "live" ? false : 15_000,
  });
  const tabs: { key: PollFilter; label: string; icon: typeof Vote }[] = [
    { key: "all", label: "All polls", icon: Vote },
    { key: "open", label: "Open", icon: ArrowDownToLine },
    { key: "scheduled", label: "Upcoming", icon: Clock3 },
    { key: "closed", label: "Closed", icon: Check },
    ...(canManage
      ? [{ key: "draft" as const, label: "Drafts", icon: CalendarDays }]
      : []),
  ];
  return (
    <div className="grid gap-6">
      <section className="relative overflow-hidden rounded-[1.7rem] bg-[#10213b] px-6 py-8 text-white sm:px-9 sm:py-10">
        <div
          className="pointer-events-none absolute -right-12 -top-16 size-72 rounded-full border-[36px] border-white/[.035]"
          aria-hidden="true"
        />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <p className="eyebrow text-gold">The association, together</p>
            <h1 className="display-type mt-3 text-3xl sm:text-4xl">
              Your voice. Our next move.
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-6 text-white/65">
              Make decisions together, one member at a time. Take part in the
              conversations that shape UTAG-UG.
            </p>
          </div>
          {canManage ? (
            <Button asChild variant="gold">
              <Link href="/dashboard/polls/new">
                <Plus className="size-4" /> Create poll
              </Link>
            </Button>
          ) : (
            <span className="inline-flex items-center gap-2 text-xs text-white/65">
              <Vote className="size-5 text-gold" /> Every eligible member has a
              voice
            </span>
          )}
        </div>
      </section>
      <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
        <div
          className="flex flex-wrap gap-1 rounded-2xl bg-panel p-1.5"
          role="group"
          aria-label="Filter polls"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                type="button"
                key={tab.key}
                aria-pressed={state === tab.key}
                onClick={() => {
                  setState(tab.key);
                  setPage(1);
                }}
                className={cn(
                  "inline-flex min-h-10 items-center gap-2 rounded-xl px-3.5 text-xs font-bold transition",
                  state === tab.key
                    ? "bg-paper text-ink shadow-sm"
                    : "text-muted hover:text-ink",
                )}
              >
                <Icon className="size-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
        <label className="flex min-h-11 items-center gap-2 rounded-xl border border-line bg-paper px-4 xl:w-72">
          <Search className="size-4 text-muted" />
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            aria-label="Search polls"
            placeholder="Search questions or titles…"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
        </label>
      </div>
      {polls.isLoading ? (
        <PollLoading />
      ) : polls.error ? (
        <PollError retry={() => polls.refetch()} />
      ) : polls.data?.items.length ? (
        <>
          <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
            {polls.data.items.map((poll) => (
              <PollListCard
                poll={poll}
                receivedAt={polls.dataUpdatedAt}
                key={poll.id}
              />
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
            <p>
              {formatNumber(polls.data.total)} poll
              {polls.data.total === 1 ? "" : "s"} · Times in Accra (GMT)
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
                aria-label="Previous page"
              >
                <ChevronLeft className="size-4" />
              </Button>
              <span>
                Page {page} of {Math.max(1, polls.data.pages)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= polls.data.pages}
                onClick={() => setPage((value) => value + 1)}
                aria-label="Next page"
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        </>
      ) : (
        <div className="workspace-folio grid justify-items-center rounded-3xl p-12 text-center">
          <Vote className="size-9 text-gold" />
          <h2 className="display-type mt-5 text-2xl">
            {search
              ? "No matching polls"
              : state === "draft"
                ? "Your next decision starts here"
                : "Room for the next conversation"}
          </h2>
          <p className="mt-3 max-w-md text-sm leading-6 text-muted">
            {search
              ? "Try a different title or question."
              : "Polls you are eligible to participate in will appear here."}
          </p>
          {canManage && !search ? (
            <Button asChild className="mt-6">
              <Link href="/dashboard/polls/new">
                <Plus className="size-4" /> Create the first poll
              </Link>
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
}
