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
import { INDUSTRIAL_ACTION_TEMPLATE, type PollInput } from "@/lib/polls";

import { PollBuilderClient } from "./poll-builder-client";

const push = vi.fn();
vi.mock("@/lib/api", () => ({ api: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
const mockedApi = vi.mocked(api);

function renderBuilder() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PollBuilderClient />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);
beforeEach(() => {
  mockedApi.mockReset();
  push.mockReset();
});

describe("poll creation", () => {
  it("does not silently switch a scheduled poll to immediate opening when its date is cleared", async () => {
    mockedApi.mockImplementation(async (path) => {
      if (path === "/api/v1/auth/me") return { permissions: ["polls.manage"] };
      if (path === "/api/v1/polls/audience-preview")
        return { eligible_count: 90 };
      throw new Error(`Unexpected request ${path}`);
    });
    renderBuilder();
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Start with the industrial action poll/,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    const immediate = screen.getByRole("checkbox", {
      name: "Open immediately when published",
    }) as HTMLInputElement;
    fireEvent.click(immediate);
    fireEvent.change(screen.getByLabelText("Opening time (GMT)"), {
      target: { value: "" },
    });
    expect(immediate.checked).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      await screen.findByText(
        "Set an opening time, or select Open immediately.",
      ),
    ).toBeTruthy();
  });

  it("saves the exact action template with confidential final votes and after-close results", async () => {
    mockedApi.mockImplementation(async (path) => {
      if (path === "/api/v1/auth/me") return { permissions: ["polls.manage"] };
      if (path === "/api/v1/polls/audience-preview")
        return { eligible_count: 90 };
      if (path === "/api/v1/polls") return { id: "draft-1", version: 1 };
      throw new Error(`Unexpected request ${path}`);
    });
    renderBuilder();
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Start with the industrial action poll/,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/dashboard/polls/draft-1"),
    );
    const created = mockedApi.mock.calls.find(
      ([path]) => path === "/api/v1/polls",
    )?.[1]?.body as PollInput;
    expect(created.question).toBe(INDUSTRIAL_ACTION_TEMPLATE.question);
    expect(created.options).toEqual(INDUSTRIAL_ACTION_TEMPLATE.options);
    expect(created.privacy).toBe("confidential");
    expect(created.allow_vote_changes).toBe(false);
    expect(created.results_visibility).toBe("after_close");
    expect(created.max_choices).toBe(1);
  });

  it("reuses the saved draft and quoted version when publishing is retried", async () => {
    let publishAttempts = 0;
    let saved: PollInput & { id: string; version: number };
    mockedApi.mockImplementation(async (path, init) => {
      if (path === "/api/v1/auth/me") return { permissions: ["polls.manage"] };
      if (path === "/api/v1/polls/audience-preview")
        return { eligible_count: 90 };
      if (path === "/api/v1/polls") {
        saved = {
          ...(init?.body as PollInput),
          id: "draft-1",
          version: 1,
        };
        return saved;
      }
      if (path === "/api/v1/polls/draft-1") {
        saved = { ...saved, version: 2 };
        return saved;
      }
      if (path === "/api/v1/polls/draft-1/publish") {
        if (!publishAttempts++) throw new Error("Temporary service failure");
        return { ...saved, status: "open" };
      }
      throw new Error(`Unexpected request ${path}`);
    });
    renderBuilder();
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Start with the industrial action poll/,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue" }));
    fireEvent.change(await screen.findByLabelText("Closing time (GMT)"), {
      target: {
        value: new Date(Date.now() + 86_400_000).toISOString().slice(0, 16),
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Publish poll" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Publish & open voting" }),
    );
    await waitFor(() => expect(publishAttempts).toBe(1));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Publish poll" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Publish & open voting" }),
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/dashboard/polls/draft-1"),
    );
    expect(
      mockedApi.mock.calls.filter(([path]) => path === "/api/v1/polls"),
    ).toHaveLength(1);
    expect(
      mockedApi.mock.calls.find(
        ([path]) => path === "/api/v1/polls/draft-1",
      )?.[1]?.headers,
    ).toEqual({ "If-Match": '"1"' });
  });
});
