import { expect, test, type Page, type WebSocketRoute } from "@playwright/test";

import { INDUSTRIAL_ACTION_TEMPLATE, type Poll, type PollInput, type PollResults } from "../lib/polls";

const pollId = "d2dc4e3f-cd8b-4cf7-bbab-af3e6a7b070a";
const optionIds = [
  "db1f5562-8d58-4a93-bc48-89443e649de3",
  "bf91e0d9-b101-4576-90c0-55490c9ae09b",
];

async function installPollMocks(page: Page, organizer = false, liveResults = false) {
  const baseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100";
  await page.context().addCookies([
    { name: "utag_session", value: "isolated-poll-browser-fixture", url: baseUrl, httpOnly: true },
    { name: "utag_csrf", value: "isolated-poll-csrf-fixture", url: baseUrl },
  ]);
  let poll: Poll = {
    id: pollId,
    ...INDUSTRIAL_ACTION_TEMPLATE,
    description: "Every eligible member has one ballot. Please read the question carefully.",
    kind: "single",
    privacy: "confidential",
    results_visibility: liveResults ? "live" : "after_close",
    allow_vote_changes: false,
    max_choices: 1,
    opens_at: new Date(Date.now() - 60_000).toISOString(),
    closes_at: new Date(Date.now() + 86_400_000).toISOString(),
    audiences: [{ type: "all_members", value: "all" }],
    options: INDUSTRIAL_ACTION_TEMPLATE.options.map((label, position) => ({ id: optionIds[position], label, position })),
    status: "open",
    published_at: new Date(Date.now() - 60_000).toISOString(),
    eligible_count: 120,
    has_voted: false,
    my_vote: null,
    can_vote: true,
    can_manage: organizer,
    can_view_results: organizer || liveResults,
    can_export: organizer,
    created_at: new Date(Date.now() - 3_600_000).toISOString(),
    version: 1,
    server_now: new Date().toISOString(),
  };
  let results: PollResults = {
    response_count: 48,
    eligible_count: 120,
    turnout_percent: 40,
    options: poll.options.map((option, index) => ({ ...option, votes: index ? 12 : 36, percent: index ? 25 : 75 })),
    timeline: [{ at: new Date(Date.now() - 3_600_000).toISOString(), responses: 48 }],
    generated_at: new Date().toISOString(),
    named_voters: null,
  };
  let socket: WebSocketRoute | undefined;
  const messages: string[] = [];
  const requests: { method: string; path: string; body: unknown }[] = [];
  await page.routeWebSocket("**/api/v1/realtime", (ws) => {
    socket = ws;
    ws.onMessage((message) => {
      const text = String(message);
      messages.push(text);
      if (text.includes("subscriptions.refresh")) {
        ws.send(JSON.stringify({ type: "subscriptions.changed", resync_required: true }));
      }
    });
    ws.send(JSON.stringify({ type: "connection.ready", resync_required: true }));
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const body = method === "GET" ? null : request.postDataJSON();
    requests.push({ method, path, body });
    let response: unknown;
    if (path === "/api/v1/auth/me") {
      response = {
        id: "191f6c4f-5f4e-4a45-8914-c2af48a9ef7b",
        full_name: organizer ? "Dr. Ama Mensah" : "Dr. Kojo Asare",
        email: "poll-preview@example.edu.gh",
        profile_media_id: null,
        must_change_password: false,
        must_complete_executive_profile: false,
        roles: [organizer ? "executive" : "member"],
        permissions: ["dashboard.view", "chat.use", "documents.view", ...(organizer ? ["polls.manage", "polls.results", "polls.export"] : [])],
      };
    } else if (path === "/api/v1/notifications/unread-count") {
      response = { unread: 0 };
    } else if (path === "/api/v1/polls/audience-preview") {
      response = { eligible_count: 120 };
    } else if (path === "/api/v1/polls/audiences") {
      response = { items: [{ type: "school", value: "ff751fe7-aef2-4730-978a-a4189dcac9d8", label: "School of Social Sciences" }], page: 1, page_size: 50, total: 1, pages: 1 };
    } else if (path === "/api/v1/polls" && method === "POST") {
      const input = body as PollInput;
      poll = { ...poll, ...input, options: input.options.map((label, position) => ({ id: optionIds[position], label, position })), status: "draft", published_at: null, can_vote: false };
      response = poll;
    } else if (path === `/api/v1/polls/${pollId}/publish`) {
      poll = { ...poll, status: "open", opens_at: poll.opens_at ?? new Date().toISOString(), published_at: new Date().toISOString(), can_vote: true, can_view_results: organizer || liveResults };
      response = poll;
    } else if (path === `/api/v1/polls/${pollId}/vote`) {
      poll = { ...poll, has_voted: true, can_vote: false, my_vote: (body as { option_ids: string[] }).option_ids };
      response = poll;
    } else if (path === `/api/v1/polls/${pollId}/results`) {
      response = results;
    } else if (path === `/api/v1/polls/${pollId}`) {
      response = { ...poll, server_now: new Date().toISOString() };
    } else if (path === "/api/v1/polls") {
      response = { items: [poll], page: 1, page_size: 12, total: 1, pages: 1 };
    } else {
      response = { items: [], page: 1, page_size: 30, total: 0, pages: 0 };
    }
    await route.fulfill({ json: response });
  });
  return {
    requests,
    messages,
    updateResults: (count = 49, notify = true) => {
      results = { ...results, response_count: count, turnout_percent: count / 120 * 100, generated_at: new Date().toISOString(), options: results.options.map((option, index) => ({ ...option, votes: index ? 12 : count - 12, percent: (index ? 12 : count - 12) / count * 100 })) };
      if (notify) socket?.send(JSON.stringify({ type: "poll.vote.cast", topic: `poll:${pollId}:results`, aggregate_id: pollId }));
    },
    disconnect: () => socket?.close({ code: 1001, reason: "Isolated recovery test" }),
  };
}

test("a member submits a confidential final ballot on mobile without fetching hidden results", async ({ page }, testInfo) => {
  const fixture = await installPollMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/dashboard/polls/${pollId}`);
  await expect(page.getByText(INDUSTRIAL_ACTION_TEMPLATE.question, { exact: true })).toBeVisible();
  const yes = page.getByRole("radio", { name: INDUSTRIAL_ACTION_TEMPLATE.options[0] });
  await yes.focus();
  expect(await yes.evaluate((element) => getComputedStyle(element).outlineStyle)).not.toBe("none");
  await page.keyboard.press("Space");
  await expect(yes).toBeChecked();
  await page.getByRole("button", { name: /submit.*vote|cast.*vote/i }).click();
  const confirmation = page.getByRole("alertdialog");
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "Confirm my vote", exact: true }).click();
  await expect.poll(() => fixture.requests.filter((item) => item.path.endsWith("/vote")).length).toBe(1);
  await expect(page.getByRole("radio", { name: INDUSTRIAL_ACTION_TEMPLATE.options[0] })).toBeDisabled();
  expect(fixture.requests.some((item) => item.path.endsWith("/results"))).toBe(false);
  await expect.poll(() => fixture.messages.some((message) => message.includes("subscriptions.refresh"))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  await expect(page.locator("[data-sonner-toast]")).toHaveCount(0, { timeout: 6_000 });
  await page.screenshot({ path: testInfo.outputPath("member-ballot-mobile.png"), fullPage: true });
});

test("organizers receive live aggregate results and a printable report", async ({ page }, testInfo) => {
  const fixture = await installPollMocks(page, true);
  await page.goto(`/dashboard/polls/${pollId}`);
  await expect(page.getByRole("heading", { name: "Live results" })).toBeVisible();
  await expect(page.getByText("48", { exact: true }).first()).toBeVisible();
  fixture.updateResults();
  await expect(page.getByText("49", { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("participation-pulse-desktop.png"), fullPage: true });
  await page.goto(`/dashboard/polls/${pollId}/print`);
  await expect(page.locator(".poll-print-report")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".poll-print-controls")).toBeHidden();
  await expect(page.locator("aside:visible")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("poll-report-print.png"), fullPage: true });
});

test("an organizer publishes the industrial-action template with the confirmed defaults", async ({ page }) => {
  const fixture = await installPollMocks(page, true);
  await page.goto("/dashboard/polls/new");
  await page.getByRole("button", { name: /start with the industrial action poll/i }).click();
  await expect(page.getByLabel("Poll question")).toHaveValue(INDUSTRIAL_ACTION_TEMPLATE.question);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("120", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByLabel("Member result visibility")).toHaveValue("after_close");
  await expect(page.getByLabel("Ballot privacy")).toHaveValue("confidential");
  await page.getByLabel("Closing time (GMT)").fill(new Date(Date.now() + 86_400_000).toISOString().slice(0, 16));
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Publish poll", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Publish & open voting" }).click();
  await expect(page).toHaveURL(new RegExp(`/dashboard/polls/${pollId}$`));
  await expect(page.getByText("Voting open", { exact: true }).first()).toBeVisible();
  const submitted = fixture.requests.find((request) => request.path === "/api/v1/polls" && request.method === "POST");
  expect(submitted?.body).toMatchObject({ privacy: "confidential", results_visibility: "after_close", allow_vote_changes: false, max_choices: 1 });
});

test("results refresh while disconnected and resync when the socket reconnects", async ({ page }) => {
  test.setTimeout(45_000);
  const fixture = await installPollMocks(page, true);
  await page.goto(`/dashboard/polls/${pollId}`);
  await expect(page.getByText("48", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Results live/)).toBeVisible();
  const initialResyncs = fixture.messages.filter((message) => message.includes("resync.complete")).length;

  // Fail only new socket attempts, keeping HTTP available for the fallback.
  await page.evaluate(() => {
    const control = window as typeof window & { restorePollSockets?: () => void };
    const nativeSocket = window.WebSocket;
    control.restorePollSockets = () => { window.WebSocket = nativeSocket; };
    window.WebSocket = class {
      static OPEN = 1;
      readyState = 0;
      onclose: ((event: CloseEvent) => void) | null = null;
      constructor() { window.setTimeout(() => this.close(), 0); }
      send() {}
      close() {
        this.readyState = 3;
        this.onclose?.(new CloseEvent("close", { code: 1006 }));
      }
    } as unknown as typeof WebSocket;
  });
  fixture.disconnect();
  await expect(page.getByText(/Refreshing every 15s/i)).toBeVisible();
  fixture.updateResults(49, false);
  await expect(page.getByText("49", { exact: true }).first()).toBeVisible({ timeout: 20_000 });

  fixture.updateResults(50, false);
  await page.evaluate(() => {
    (window as typeof window & { restorePollSockets?: () => void }).restorePollSockets?.();
  });
  await expect(page.getByText(/Results live/)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("50", { exact: true }).first()).toBeVisible();
  await expect.poll(() => fixture.messages.filter((message) => message.includes("resync.complete")).length).toBeGreaterThan(initialResyncs);
});
