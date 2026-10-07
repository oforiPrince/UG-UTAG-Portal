"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Clock3,
  LoaderCircle,
  Radio,
  RefreshCw,
  Vote,
} from "lucide-react";
import { useEffect, useState } from "react";

import { useRealtime } from "@/components/realtime-provider";
import { Button } from "@/components/ui/button";
import { type Poll, type PollStatus } from "@/lib/polls";
import { cn } from "@/lib/utils";

export function PollStatusBadge({ status }: { status: PollStatus }) {
  const Icon = status === "open" ? Radio : status === "closed" ? Check : Clock3;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[.65rem] font-bold",
        status === "open" ? "bg-sky/10 text-coral" : "bg-ink/5 text-muted",
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {status === "open"
        ? "Voting open"
        : status === "scheduled"
          ? "Upcoming"
          : status === "closed"
            ? "Closed"
            : "Draft"}
    </span>
  );
}

export function PollLoading({ label = "Loading polls…" }: { label?: string }) {
  return (
    <div
      className="workspace-folio grid min-h-80 place-items-center rounded-3xl p-10"
      role="status"
    >
      <span className="grid justify-items-center gap-3 text-sm text-muted">
        <LoaderCircle className="size-6 animate-spin text-coral" />
        {label}
      </span>
    </div>
  );
}

export function PollError({
  retry,
  message = "The poll could not be loaded. Your account may no longer have access.",
}: {
  retry: () => void;
  message?: string;
}) {
  return (
    <div className="workspace-folio grid justify-items-center rounded-3xl p-10 text-center">
      <Vote className="size-8 text-gold" />
      <h2 className="display-type mt-4 text-2xl">Let’s try that again</h2>
      <p className="mt-3 max-w-md text-sm leading-6 text-muted">{message}</p>
      <Button variant="outline" onClick={retry} className="mt-6">
        <RefreshCw className="size-4" /> Try again
      </Button>
    </div>
  );
}

export function usePollClock(serverNow?: string, receivedAt?: number) {
  const [localNow, setLocalNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setLocalNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  const correction =
    serverNow && receivedAt ? Date.parse(serverNow) - receivedAt : 0;
  return localNow + correction;
}

export function usePollBoundaryRefresh(poll?: Poll, receivedAt?: number) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!poll || !poll.published_at) return;
    const correction =
      poll.server_now && receivedAt
        ? Date.parse(poll.server_now) - receivedAt
        : 0;
    const correctedNow = Date.now() + correction;
    const boundaries = [
      poll.status === "scheduled" ? poll.opens_at : null,
      poll.status !== "closed" ? poll.closes_at : null,
    ]
      .filter((value): value is string => Boolean(value))
      .map(Date.parse)
      .filter((value) => value > correctedNow);
    if (!boundaries.length) return;
    const wait = Math.min(
      Math.min(...boundaries) - correctedNow + 100,
      2_147_483_647,
    );
    const timer = window.setTimeout(
      () => queryClient.invalidateQueries({ queryKey: ["polls"] }),
      wait,
    );
    return () => window.clearTimeout(timer);
  }, [poll, queryClient, receivedAt]);
}

export function PollLiveLabel({ refreshedAt }: { refreshedAt?: string }) {
  const { state } = useRealtime();
  return (
    <span
      className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 text-[.68rem] text-muted"
      role="status"
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          state === "live" ? "bg-sky" : "bg-gold",
        )}
      />
      {state === "live"
        ? "Results live"
        : state === "connecting"
          ? "Reconnecting · refreshing every 15s"
          : "Refreshing every 15s"}
      {refreshedAt ? (
        <span>
          ·{" "}
          {new Intl.DateTimeFormat("en-GH", {
            timeZone: "Africa/Accra",
            timeStyle: "short",
          }).format(new Date(refreshedAt))}{" "}
          GMT
        </span>
      ) : null}
    </span>
  );
}
