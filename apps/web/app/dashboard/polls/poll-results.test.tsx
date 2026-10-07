import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Poll, PollResults } from "@/lib/polls";

import { PollResultsPanel } from "./poll-results";

const chartAnimations = vi.hoisted(() => ({ values: [] as boolean[] }));
vi.mock("motion/react", () => ({ useReducedMotion: () => true }));
vi.mock("@/components/realtime-provider", () => ({
  useRealtime: () => ({ state: "live" }),
}));
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  AreaChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Area: ({ isAnimationActive }: { isAnimationActive: boolean }) => {
    chartAnimations.values.push(isAnimationActive);
    return null;
  },
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

const poll: Poll = {
  id: "poll-results-1",
  title: "Association priorities",
  question: "Which priorities should we focus on?",
  description: "Select the priorities that matter to you.",
  kind: "multiple",
  privacy: "confidential",
  results_visibility: "live",
  allow_vote_changes: false,
  max_choices: 2,
  opens_at: "2026-10-07T08:00:00Z",
  closes_at: "2026-10-08T08:00:00Z",
  audiences: [{ type: "all_members" }],
  options: [
    { id: "arrears", label: "Promotion arrears", position: 0 },
    { id: "research", label: "Research support", position: 1 },
  ],
  status: "open",
  published_at: "2026-10-07T08:00:00Z",
  eligible_count: 100,
  has_voted: false,
  my_vote: null,
  can_vote: true,
  can_manage: true,
  can_view_results: true,
  can_export: true,
  created_at: "2026-10-06T08:00:00Z",
  version: 1,
  server_now: "2026-10-07T12:00:00Z",
};

function resultsFixture(): PollResults {
  return {
    response_count: 0,
    eligible_count: 100,
    turnout_percent: 0,
    options: poll.options.map((option) => ({
      ...option,
      votes: 0,
      percent: 0,
    })),
    timeline: [],
    generated_at: "2026-10-07T12:00:00Z",
    named_voters: null,
  };
}

afterEach(cleanup);
beforeEach(() => {
  chartAnimations.values.length = 0;
});

describe("aggregate poll results", () => {
  it("shows zero turnout, zero answer percentages, and a useful empty state before anyone votes", () => {
    render(<PollResultsPanel poll={poll} results={resultsFixture()} />);

    expect(
      screen.getByRole("img", {
        name: "0.0 percent turnout, 0 of 100 eligible members",
      }),
    ).toBeTruthy();
    expect(screen.getByText("0", { exact: true })).toBeTruthy();
    expect(screen.getAllByText("0.0%", { exact: true })).toHaveLength(3);
    for (const option of poll.options) {
      const bar = screen.getByRole("progressbar", { name: option.label });
      expect(bar.getAttribute("aria-valuenow")).toBe("0");
      expect((bar.firstElementChild as HTMLElement).style.width).toBe("0%");
    }
    expect(
      screen.getByText("The first vote will start the story."),
    ).toBeTruthy();
    expect(screen.queryByText(/NaN|Infinity/)).toBeNull();
  });

  it("preserves multiple-choice percentages per respondent and hides confidential voter identities", () => {
    const results: PollResults = {
      ...resultsFixture(),
      response_count: 10,
      turnout_percent: 10,
      options: poll.options.map((option, index) => ({
        ...option,
        votes: index ? 7 : 8,
        percent: index ? 70 : 80,
      })),
      timeline: [{ at: "2026-10-07T11:00:00Z", responses: 10 }],
    };
    render(<PollResultsPanel poll={poll} results={results} />);

    expect(screen.getByText("10", { exact: true })).toBeTruthy();
    expect(screen.queryByText("15", { exact: true })).toBeNull();
    expect(
      screen.getByRole("img", {
        name: "10.0 percent turnout, 10 of 100 eligible members",
      }),
    ).toBeTruthy();
    expect(screen.getByText("80.0%", { exact: true })).toBeTruthy();
    expect(screen.getByText("70.0%", { exact: true })).toBeTruthy();
    for (const [index, option] of poll.options.entries()) {
      const bar = screen.getByRole("progressbar", { name: option.label });
      const percent = index ? "70" : "80";
      expect(bar.getAttribute("aria-valuenow")).toBe(percent);
      expect((bar.firstElementChild as HTMLElement).style.width).toBe(
        `${percent}%`,
      );
    }
    expect(
      screen.getByText(/share of respondents selecting each answer/),
    ).toBeTruthy();
    expect(
      screen.getByText(/percentages can add up to more than 100%/),
    ).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText("Named ballot record")).toBeNull();
    expect(chartAnimations.values).toEqual([false]);
  });

  it("renders named voter choices and keeps report sections intact when printed", () => {
    const results: PollResults = {
      ...resultsFixture(),
      response_count: 1,
      turnout_percent: 1,
      timeline: [{ at: "2026-10-07T11:00:00Z", responses: 1 }],
      named_voters: [
        {
          member_name: "Dr. Demo Voter 01",
          option_labels: ["Promotion arrears", "Research support"],
        },
      ],
    };
    const { container } = render(
      <PollResultsPanel
        poll={{ ...poll, privacy: "named" }}
        results={results}
        print
      />,
    );

    expect(screen.getByText("Named ballot record")).toBeTruthy();
    expect(screen.getByText("Dr. Demo Voter 01")).toBeTruthy();
    expect(
      screen.getByText("Promotion arrears; Research support"),
    ).toBeTruthy();
    expect(container.querySelectorAll("[data-poll-result]")).toHaveLength(3);
    expect(chartAnimations.values).toEqual([false]);
  });
});
