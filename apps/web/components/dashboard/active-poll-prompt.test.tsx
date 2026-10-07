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
import type { Poll } from "@/lib/polls";

import { ActivePollPrompt } from "./active-poll-prompt";

vi.mock("@/lib/api", () => ({ api: vi.fn() }));

const mockedApi = vi.mocked(api);

function poll(overrides: Partial<Poll> = {}): Poll {
  return {
    id: "poll-1",
    title: "Member priorities",
    question: "Which priority should the association pursue first?",
    description: "",
    kind: "single",
    privacy: "confidential",
    results_visibility: "after_close",
    allow_vote_changes: false,
    max_choices: 1,
    opens_at: new Date(Date.now() - 60_000).toISOString(),
    closes_at: new Date(Date.now() + 3_600_000).toISOString(),
    closed_at: null,
    audiences: [{ type: "all_members", value: "all" }],
    options: [
      { id: "option-1", label: "Priority one", position: 0 },
      { id: "option-2", label: "Priority two", position: 1 },
    ],
    status: "open",
    published_at: new Date(Date.now() - 60_000).toISOString(),
    eligible_count: 12,
    has_voted: false,
    my_vote: null,
    can_vote: true,
    can_manage: false,
    can_view_results: false,
    can_export: false,
    created_at: new Date(Date.now() - 60_000).toISOString(),
    version: 2,
    server_now: new Date().toISOString(),
    ...overrides,
  };
}

function renderPrompt(pathname = "/dashboard", userId = "member-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ActivePollPrompt enabled pathname={pathname} userId={userId} />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("ActivePollPrompt", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockedApi.mockReset();
  });

  it("prompts an eligible non-voter with the most urgent active poll", async () => {
    const later = poll({
      id: "poll-later",
      title: "Later decision",
      closes_at: new Date(Date.now() + 7_200_000).toISOString(),
    });
    mockedApi.mockResolvedValue({
      items: [later, poll()],
      page: 1,
      page_size: 20,
      total: 2,
      pages: 1,
    });

    renderPrompt();

    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Member priorities" }),
    ).toBeTruthy();
    expect(
      screen.getByText("2 active polls are waiting for your response."),
    ).toBeTruthy();
    expect(
      screen.getByRole("link", { name: /Vote now/i }).getAttribute("href"),
    ).toBe("/dashboard/polls/poll-1");
  });

  it("snoozes a poll for this member and restores the preference", async () => {
    mockedApi.mockResolvedValue({
      items: [poll()],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });
    const first = renderPrompt();
    fireEvent.click(
      await screen.findByRole("button", { name: "Remind me later" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    first.unmount();

    renderPrompt();
    await waitFor(() => expect(mockedApi).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("does not interrupt a voted member or the poll currently being viewed", async () => {
    mockedApi.mockResolvedValue({
      items: [poll({ has_voted: true, can_vote: false })],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });
    const voted = renderPrompt();
    await waitFor(() => expect(mockedApi).toHaveBeenCalledOnce());
    expect(screen.queryByRole("dialog")).toBeNull();
    voted.unmount();

    mockedApi.mockClear();
    mockedApi.mockResolvedValue({
      items: [poll()],
      page: 1,
      page_size: 20,
      total: 1,
      pages: 1,
    });
    renderPrompt("/dashboard/polls/poll-1");
    await waitFor(() => expect(mockedApi).toHaveBeenCalledOnce());
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
