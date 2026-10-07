"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock3, LockKeyhole, Vote, X } from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  formatPollDate,
  pollCountdown,
  type Poll,
  type PollPage,
} from "@/lib/polls";

const SNOOZE_MS = 4 * 60 * 60 * 1_000;
const storagePrefix = (userId: string) => `utag:poll-prompt:${userId}:`;
const subscribeToHydration = () => () => undefined;
const hydratedSnapshot = () => true;
const serverSnapshot = () => false;

function snoozedUntil(userId: string, pollId: string) {
  return Number(
    window.localStorage.getItem(`${storagePrefix(userId)}${pollId}`),
  );
}

export function ActivePollPrompt({
  enabled,
  pathname,
  userId,
}: {
  enabled: boolean;
  pathname: string;
  userId: string;
}) {
  const isPollWorkspace = pathname.startsWith("/dashboard/polls");
  const dialogRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(0);
  const [snoozedPollIds, setSnoozedPollIds] = useState<Set<string>>(
    () => new Set(),
  );
  const hydrated = useSyncExternalStore(
    subscribeToHydration,
    hydratedSnapshot,
    serverSnapshot,
  );
  const polls = useQuery({
    queryKey: ["polls", "active-prompt", userId],
    queryFn: () =>
      api<PollPage<Poll>>(
        "/api/v1/polls?state=open&eligible_only=true&page_size=20",
      ),
    enabled: enabled && !isPollWorkspace,
    refetchInterval: 60_000,
  });

  useEffect(() => {
    const initial = window.setTimeout(() => setNow(Date.now()), 0);
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(interval);
    };
  }, []);

  const pendingPolls = useMemo(() => {
    if (!hydrated || !now || isPollWorkspace) return [];
    return (polls.data?.items ?? [])
      .filter(
        (poll) =>
          poll.status === "open" &&
          poll.can_vote &&
          !poll.has_voted &&
          Boolean(poll.closes_at) &&
          Date.parse(poll.closes_at ?? "") > now &&
          !snoozedPollIds.has(poll.id) &&
          snoozedUntil(userId, poll.id) <= now,
      )
      .sort(
        (left, right) =>
          Date.parse(left.closes_at ?? "") - Date.parse(right.closes_at ?? ""),
      );
  }, [hydrated, isPollWorkspace, now, polls.data?.items, snoozedPollIds, userId]);
  const poll = pendingPolls[0];

  const snooze = useCallback(
    (pollId: string) => {
      const until = Date.now() + SNOOZE_MS;
      window.localStorage.setItem(
        `${storagePrefix(userId)}${pollId}`,
        String(until),
      );
      setSnoozedPollIds((current) => new Set(current).add(pollId));
    },
    [userId],
  );

  useEffect(() => {
    if (!poll) return;
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const frame = window.requestAnimationFrame(() =>
      dialogRef.current?.querySelector<HTMLElement>("a[href]")?.focus(),
    );
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        snooze(poll.id);
        return;
      }
      if (event.key !== "Tab") return;
      const controls = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      if (!controls.length) return;
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus();
    };
  }, [poll, snooze]);

  if (!poll || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[120] flex items-end justify-center bg-ink/30 px-0 backdrop-blur-[2px] sm:items-center sm:p-5"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) snooze(poll.id);
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="active-poll-prompt-title"
        aria-describedby="active-poll-prompt-question"
        className="w-full max-w-lg overflow-hidden rounded-t-[2rem] bg-paper shadow-[0_36px_110px_rgba(4,16,31,.4)] sm:rounded-[2rem]"
      >
        <div className="relative overflow-hidden bg-[#091529] px-6 pt-7 pb-6 text-white sm:px-8 sm:pt-8">
          <div
            className="absolute -top-14 -right-10 size-40 rounded-full border-[22px] border-gold/15"
            aria-hidden="true"
          />
          <div className="relative flex items-start gap-4">
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-gold text-[#172035] shadow-lg shadow-black/15">
              <Vote className="size-5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[.62rem] font-black tracking-[.18em] text-gold uppercase">
                Your voice is needed
              </p>
              <h2
                id="active-poll-prompt-title"
                className="display-type mt-2 text-2xl leading-tight text-white sm:text-[1.75rem]"
              >
                {poll.title}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => snooze(poll.id)}
              className="-mr-2 grid size-10 shrink-0 place-items-center rounded-full text-white/55 transition hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold"
              aria-label="Remind me about this poll later"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        <div className="px-6 py-6 sm:px-8 sm:py-7">
          <p
            id="active-poll-prompt-question"
            className="text-base font-bold leading-7 text-ink"
          >
            {poll.question}
          </p>
          <div className="mt-5 grid gap-2 rounded-2xl border border-line bg-panel/55 p-4 text-xs text-muted sm:grid-cols-2">
            <span className="flex items-center gap-2 font-semibold text-ink">
              <Clock3 className="size-4 text-coral" aria-hidden="true" />
              {pollCountdown(poll.closes_at, now)}
            </span>
            <span className="flex items-center gap-2 sm:justify-end">
              <LockKeyhole className="size-4 text-gold" aria-hidden="true" />
              {poll.privacy === "confidential"
                ? "Confidential ballot"
                : "Named ballot"}
            </span>
            <span className="sm:col-span-2">
              Closes {formatPollDate(poll.closes_at)} GMT
            </span>
          </div>
          {pendingPolls.length > 1 ? (
            <p className="mt-3 text-[.68rem] font-semibold text-muted">
              {pendingPolls.length} active polls are waiting for your response.
            </p>
          ) : null}
          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="ghost"
              onClick={() => snooze(poll.id)}
            >
              Remind me later
            </Button>
            <Button asChild variant="gold">
              <Link href={`/dashboard/polls/${poll.id}`}>
                Vote now <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
