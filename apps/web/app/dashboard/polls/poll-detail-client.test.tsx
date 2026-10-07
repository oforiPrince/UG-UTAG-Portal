import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { type Poll } from "@/lib/polls";

import { PollDetailClient } from "./poll-detail-client";

const refreshSubscriptions = vi.fn();
vi.mock("@/lib/api", () => ({ api: vi.fn(), API_URL: "" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/components/realtime-provider", () => ({
  useRealtime: () => ({ state: "live", refreshSubscriptions }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./poll-results", () => ({
  PollResultsPanel: () => <div>Aggregate result panel</div>,
}));

const mockedApi = vi.mocked(api);
const fixture = (): Poll => ({
  id: "poll-1",
  title: "Association decision",
  question: "Do you support this proposal?",
  description: "Please consider the full proposal.",
  kind: "single",
  privacy: "confidential",
  results_visibility: "after_close",
  allow_vote_changes: false,
  max_choices: 1,
  opens_at: new Date(Date.now() - 60_000).toISOString(),
  closes_at: new Date(Date.now() + 3_600_000).toISOString(),
  audiences: [{ type: "all_members" }],
  options: [
    { id: "yes", label: "YES, I support", position: 0 },
    { id: "no", label: "NO, I do not support", position: 1 },
  ],
  status: "open",
  published_at: new Date(Date.now() - 60_000).toISOString(),
  eligible_count: 100,
  has_voted: false,
  my_vote: null,
  can_vote: true,
  can_manage: false,
  can_view_results: false,
  can_export: false,
  created_at: new Date().toISOString(),
  version: 1,
  server_now: new Date().toISOString(),
});
function renderPoll() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PollDetailClient pollId="poll-1" />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);
beforeEach(() => {
  mockedApi.mockReset();
  refreshSubscriptions.mockReset();
});

describe("member ballot", () => {
  it("keeps after-close totals out of requests and records the member’s final selection", async () => {
    let poll = fixture();
    mockedApi.mockImplementation(async (path, init) => {
      if (path === "/api/v1/polls/poll-1/vote") {
        poll = {
          ...poll,
          has_voted: true,
          my_vote: (init?.body as { option_ids: string[] }).option_ids,
          can_vote: false,
        };
        return poll;
      }
      if (path === "/api/v1/polls/poll-1") return poll;
      throw new Error(`Unexpected request ${path}`);
    });
    renderPoll();
    fireEvent.click(
      await screen.findByRole("radio", { name: "YES, I support" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit my vote" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Confirm my vote" }),
    );
    expect(await screen.findByText("Your vote is recorded")).toBeTruthy();
    await waitFor(() => expect(refreshSubscriptions).toHaveBeenCalled());
    const recorded = screen.getByRole("radio", {
      name: "YES, I support",
    }) as HTMLInputElement;
    expect(recorded.checked).toBe(true);
    expect(recorded.closest("fieldset")?.disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Update my vote" })).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Results when voting closes" }),
    ).toBeTruthy();
    expect(
      mockedApi.mock.calls.some(([path]) => path.endsWith("/results")),
    ).toBe(false);
    expect(mockedApi).toHaveBeenCalledWith("/api/v1/polls/poll-1/vote", {
      method: "PUT",
      body: { option_ids: ["yes"] },
    });
  });

  it("requests authorized results and permits a configured vote update", async () => {
    const poll = {
      ...fixture(),
      has_voted: true,
      my_vote: ["yes"],
      allow_vote_changes: true,
      can_view_results: true,
      results_visibility: "after_vote" as const,
    };
    mockedApi.mockImplementation(async (path) =>
      path.endsWith("/results")
        ? {
            response_count: 1,
            eligible_count: 100,
            turnout_percent: 1,
            options: [],
            timeline: [],
            named_voters: null,
            generated_at: new Date().toISOString(),
          }
        : poll,
    );
    renderPoll();
    expect(await screen.findByText("Aggregate result panel")).toBeTruthy();
    const update = screen.getByRole("button", {
      name: "Update my vote",
    }) as HTMLButtonElement;
    expect(update.disabled).toBe(true);
    fireEvent.click(
      screen.getByRole("radio", { name: "NO, I do not support" }),
    );
    expect(update.disabled).toBe(false);
  });

  it("refreshes at the server-corrected closing boundary", async () => {
    const poll = {
      ...fixture(),
      closes_at: new Date(Date.now() + 120).toISOString(),
    };
    mockedApi.mockResolvedValue(poll);
    renderPoll();
    await screen.findByRole("heading", { name: "Association decision" });
    await waitFor(() =>
      expect(
        mockedApi.mock.calls.filter(([path]) => path === "/api/v1/polls/poll-1")
          .length,
      ).toBeGreaterThan(1),
    );
  });

  it("reuses a reminder request key when an organizer retries a failed send", async () => {
    const poll = { ...fixture(), can_manage: true };
    let attempts = 0;
    mockedApi.mockImplementation(async (path) => {
      if (path.endsWith("/reminders/preview")) return { recipient_count: 7 };
      if (path.endsWith("/reminders")) {
        attempts += 1;
        if (attempts === 1) throw new Error("Temporary service failure");
        return { recipient_count: 7 };
      }
      return poll;
    });
    renderPoll();
    fireEvent.click(
      await screen.findByRole("button", { name: "Remind non-voters" }),
    );
    await screen.findByText(/7 eligible members have not voted/);
    fireEvent.click(screen.getByRole("button", { name: "Review reminder" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Send reminder" }),
    );
    await waitFor(() => expect(attempts).toBe(1));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Review reminder" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Send reminder" }),
    );
    await waitFor(() => expect(attempts).toBe(2));
    const headers = mockedApi.mock.calls
      .filter(([path]) => path.endsWith("/reminders"))
      .map(([, init]) => init?.headers);
    expect(headers[0]).toEqual(headers[1]);
    expect(new Headers(headers[0]).get("Idempotency-Key")).toMatch(
      /^[0-9a-f-]{36}$/,
    );
  });
});
