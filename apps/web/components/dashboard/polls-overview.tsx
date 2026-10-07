"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Vote } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatPollDate, type Poll, type PollPage } from "@/lib/polls";

export function PollsOverview() {
  const query = useQuery({
    queryKey: ["polls", "overview"],
    queryFn: () =>
      api<PollPage<Poll>>(
        "/api/v1/polls?state=open&eligible_only=true&page_size=3",
      ),
    refetchInterval: 60_000,
  });
  if (query.isLoading || query.error || !query.data?.items.length) return null;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="eyebrow text-coral">Your voice</p>
            <h3 className="mt-2 text-lg font-black">Decisions happening now</h3>
          </div>
          <Vote className="size-5 text-gold" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="divide-y divide-line">
          {query.data.items.map((poll) => (
            <Link
              href={`/dashboard/polls/${poll.id}`}
              key={poll.id}
              className="flex items-center gap-3 py-4 first:pt-1"
            >
              <span className="min-w-0 flex-1">
                <b className="block text-sm leading-5">{poll.title}</b>
                <small className="mt-1 block text-[.68rem] text-muted">
                  {poll.has_voted ? "You voted" : "Have your say"} · Closes{" "}
                  {formatPollDate(poll.closes_at)} GMT
                </small>
              </span>
              <ArrowRight className="size-4 shrink-0 text-coral" />
            </Link>
          ))}
        </div>
        <Link
          href="/dashboard/polls"
          className="mt-4 inline-flex items-center gap-2 text-xs font-bold text-coral"
        >
          All polls <ArrowRight className="size-3.5" />
        </Link>
      </CardContent>
    </Card>
  );
}
