"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Printer } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  formatPollDate,
  pollRules,
  type Poll,
  type PollResults,
} from "@/lib/polls";

import { PollResultsPanel } from "./poll-results";
import { PollError, PollLoading, PollStatusBadge } from "./poll-ui";

export function PollPrintClient({ pollId }: { pollId: string }) {
  const poll = useQuery({
    queryKey: ["polls", "detail", pollId],
    queryFn: () => api<Poll>(`/api/v1/polls/${pollId}`),
  });
  const results = useQuery({
    queryKey: ["polls", "results", pollId],
    queryFn: () => api<PollResults>(`/api/v1/polls/${pollId}/results`),
    enabled: poll.data?.can_view_results === true,
  });
  if (poll.isLoading || (poll.data?.can_view_results && results.isLoading))
    return <PollLoading label="Preparing the poll report…" />;
  if (poll.error || !poll.data)
    return <PollError retry={() => poll.refetch()} />;
  if (!poll.data.can_view_results)
    return (
      <div className="workspace-folio rounded-3xl p-10 text-center">
        <h1 className="display-type text-2xl">Results are not available yet</h1>
        <p className="mt-3 text-sm text-muted">
          This report follows the poll’s result visibility rules.
        </p>
        <Button asChild className="mt-6">
          <Link href={`/dashboard/polls/${pollId}`}>Return to poll</Link>
        </Button>
      </div>
    );
  if (results.error || !results.data)
    return <PollError retry={() => results.refetch()} />;
  const data = poll.data;
  return (
    <div className="poll-print-report mx-auto grid max-w-4xl gap-6">
      <div className="poll-print-controls flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="ghost">
          <Link href={`/dashboard/polls/${pollId}`}>
            <ArrowLeft className="size-4" /> Back to poll
          </Link>
        </Button>
        <Button onClick={() => window.print()}>
          <Printer className="size-4" /> Print / save PDF
        </Button>
      </div>
      <header className="border-b border-line pb-6">
        <p className="eyebrow text-coral">UTAG-UG · Poll report</p>
        <div className="mt-4">
          <PollStatusBadge status={data.status} />
        </div>
        <h1 className="display-type mt-4 text-3xl">{data.title}</h1>
        <p className="mt-4 text-lg font-semibold leading-7">{data.question}</p>
        {data.description ? (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted">
            {data.description}
          </p>
        ) : null}
        <dl className="mt-5 grid gap-3 text-xs sm:grid-cols-2">
          <div>
            <dt className="text-muted">Voting window · Accra (GMT)</dt>
            <dd className="mt-1">
              {formatPollDate(data.opens_at)} →{" "}
              {formatPollDate(data.closed_at ?? data.closes_at)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Report generated · Accra (GMT)</dt>
            <dd className="mt-1">
              {formatPollDate(results.data.generated_at)}
            </dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-muted">{pollRules(data).privacy}</p>
      </header>
      <PollResultsPanel poll={data} results={results.data} print />
      <footer className="border-t border-line pt-4 text-[.65rem] leading-5 text-muted">
        Poll reference: {data.id} ·{" "}
        {data.status === "closed"
          ? "Final results at report generation"
          : "Voting is still in progress; these results are a snapshot"}
        .{" "}
        {data.kind === "multiple"
          ? "Members could select multiple answers."
          : "Each respondent selected one answer."}
      </footer>
    </div>
  );
}
