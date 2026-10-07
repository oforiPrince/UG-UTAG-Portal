"use client";

import { Activity, BarChart3, Users } from "lucide-react";
import { useReducedMotion } from "motion/react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { type Poll, type PollResults } from "@/lib/polls";
import { formatNumber } from "@/lib/utils";

import { PollLiveLabel } from "./poll-ui";

export function TurnoutRing({
  percent,
  count,
  eligible,
}: {
  percent: number;
  count: number;
  eligible: number;
}) {
  const value = Math.max(0, Math.min(100, percent));
  const circumference = 2 * Math.PI * 49;
  return (
    <div className="relative size-36 shrink-0">
      <svg
        viewBox="0 0 120 120"
        className="size-full -rotate-90"
        role="img"
        aria-label={`${value.toFixed(1)} percent turnout, ${count} of ${eligible} eligible members`}
      >
        <circle
          cx="60"
          cy="60"
          r="49"
          fill="none"
          stroke="currentColor"
          strokeWidth="7"
          className="text-ink/7"
        />
        <circle
          cx="60"
          cy="60"
          r="49"
          fill="none"
          stroke="var(--gold)"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - value / 100)}
          className="transition-[stroke-dashoffset] duration-700 motion-reduce:transition-none"
        />
      </svg>
      <div className="absolute inset-0 grid content-center justify-items-center">
        <b className="display-type text-3xl">{value.toFixed(1)}%</b>
        <span className="mt-1 text-[.65rem] text-muted">turnout</span>
      </div>
    </div>
  );
}

export function PollResultsPanel({
  poll,
  results,
  print = false,
}: {
  poll: Poll;
  results: PollResults;
  print?: boolean;
}) {
  const reducedMotion = useReducedMotion();
  const colors = ["var(--coral)", "var(--gold)", "var(--sky)", "var(--muted)"];
  return (
    <div className="grid min-w-0 gap-5">
      <section
        data-poll-result
        className="workspace-folio min-w-0 rounded-[1.5rem] p-6 sm:p-7"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="eyebrow text-coral">Participation pulse</p>
            <h2 className="display-type mt-2 text-2xl">
              {poll.status === "closed" ? "Final results" : "Live results"}
            </h2>
          </div>
          {!print ? <PollLiveLabel refreshedAt={results.generated_at} /> : null}
        </div>
        <div className="mt-7 flex flex-wrap items-center gap-6">
          <TurnoutRing
            percent={results.turnout_percent}
            count={results.response_count}
            eligible={results.eligible_count}
          />
          <div>
            <p className="display-type text-4xl">
              {formatNumber(results.response_count)}
            </p>
            <p className="mt-2 text-sm text-muted">
              member{results.response_count === 1 ? " has" : "s have"} responded
            </p>
            <p className="mt-3 flex items-center gap-2 text-xs text-muted">
              <Users className="size-3.5" /> of{" "}
              {formatNumber(results.eligible_count)} eligible members
            </p>
          </div>
        </div>
        <div className="workspace-rule mt-7" />
        <div className="mt-6 grid gap-5">
          {results.options.map((option, index) => (
            <div key={option.id}>
              <div className="flex items-end justify-between gap-4">
                <span className="max-w-[75%] text-sm font-semibold leading-6">
                  {option.label}
                </span>
                <span className="shrink-0 text-right">
                  <b className="block text-sm">{option.percent.toFixed(1)}%</b>
                  <span className="text-xs text-muted">
                    {formatNumber(option.votes)} vote
                    {option.votes === 1 ? "" : "s"}
                  </span>
                </span>
              </div>
              <div
                className="mt-2 h-2 overflow-hidden rounded-full bg-ink/5"
                role="progressbar"
                aria-label={option.label}
                aria-valuenow={option.percent}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full transition-[width] duration-700 motion-reduce:transition-none"
                  style={{
                    width: `${Math.max(0, Math.min(100, option.percent))}%`,
                    background: colors[index % colors.length],
                  }}
                />
              </div>
            </div>
          ))}
        </div>
        {!results.response_count ? (
          <p className="mt-6 rounded-xl bg-panel p-4 text-sm text-muted">
            The first vote will start the story.
          </p>
        ) : null}
        {poll.kind === "multiple" ? (
          <p className="mt-5 text-xs leading-5 text-muted">
            Percentages show the share of respondents selecting each answer.
            Members may select several answers, so percentages can add up to
            more than 100%.
          </p>
        ) : null}
      </section>
      {results.timeline.length ? (
        <section
          data-poll-result
          className="workspace-folio min-w-0 rounded-[1.5rem] p-6 sm:p-7"
        >
          <div className="flex items-center gap-2">
            <Activity className="size-4 text-gold" />
            <h3 className="text-sm font-black">The response over time</h3>
          </div>
          <p className="mt-2 text-xs text-muted">
            Member responses by time · Accra (GMT)
          </p>
          <div className="mt-5 h-48 min-w-0 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={results.timeline}
                margin={{ top: 8, right: 8, bottom: 0, left: -26 }}
              >
                <CartesianGrid
                  vertical={false}
                  stroke="var(--line)"
                  strokeDasharray="3 4"
                />
                <XAxis
                  dataKey="at"
                  axisLine={false}
                  tickLine={false}
                  fontSize={10}
                  tickFormatter={(value: string) =>
                    new Intl.DateTimeFormat("en-GH", {
                      timeZone: "Africa/Accra",
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(new Date(value))
                  }
                  minTickGap={32}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  fontSize={10}
                  allowDecimals={false}
                />
                <Tooltip
                  labelFormatter={(value) =>
                    new Intl.DateTimeFormat("en-GH", {
                      timeZone: "Africa/Accra",
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(String(value)))
                  }
                  contentStyle={{
                    background: "var(--paper)",
                    border: "1px solid var(--line)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                />
                <Area
                  name="Responses"
                  type="monotone"
                  dataKey="responses"
                  stroke="var(--coral)"
                  fill="var(--coral)"
                  fillOpacity={0.1}
                  strokeWidth={2.5}
                  isAnimationActive={!print && !reducedMotion}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
      {results.named_voters !== null ? (
        <section
          data-poll-result
          className="workspace-folio min-w-0 rounded-[1.5rem] p-6 sm:p-7"
        >
          <h3 className="flex items-center gap-2 text-sm font-black">
            <BarChart3 className="size-4 text-coral" /> Named ballot record
          </h3>
          <p className="mt-2 text-xs text-muted">
            Visible to authorized organizers under this poll’s named-ballot
            rule.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-80 text-left text-xs">
              <thead>
                <tr className="border-b border-line text-muted">
                  <th className="py-3 pr-4 font-semibold">Member</th>
                  <th className="py-3 font-semibold">Choices</th>
                </tr>
              </thead>
              <tbody>
                {results.named_voters.map((voter, index) => (
                  <tr
                    className="border-b border-line/60"
                    key={`${voter.member_name}:${index}`}
                  >
                    <td className="py-3 pr-4 align-top font-semibold">
                      {voter.member_name}
                    </td>
                    <td className="py-3 leading-5">
                      {voter.option_labels.join("; ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
