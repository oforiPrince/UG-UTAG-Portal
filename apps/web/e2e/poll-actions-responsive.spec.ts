import { expect, test, type Page } from "@playwright/test";

import type { Poll, PollResults } from "../lib/polls";

const pollId = "d2dc4e3f-cd8b-4cf7-bbab-af3e6a7b070a";
const now = new Date();
const poll: Poll = {
  id: pollId,
  title: "Member priorities",
  question: "Which priorities should guide the association?",
  description: "A responsive organizer action test.",
  kind: "single",
  privacy: "named",
  results_visibility: "live",
  allow_vote_changes: false,
  max_choices: 1,
  opens_at: new Date(now.getTime() - 60_000).toISOString(),
  closes_at: new Date(now.getTime() + 86_400_000).toISOString(),
  audiences: [{ type: "all_members", value: "all" }],
  options: [
    { id: "option-one", label: "Promotion arrears", position: 0 },
    { id: "option-two", label: "Research support", position: 1 },
  ],
  status: "open",
  published_at: new Date(now.getTime() - 60_000).toISOString(),
  eligible_count: 12,
  has_voted: false,
  my_vote: null,
  can_vote: false,
  can_manage: true,
  can_view_results: true,
  can_export: true,
  created_at: new Date(now.getTime() - 3_600_000).toISOString(),
  version: 1,
  server_now: now.toISOString(),
};
const results: PollResults = {
  response_count: 10,
  eligible_count: 12,
  turnout_percent: 83.33,
  options: poll.options.map((option, index) => ({
    ...option,
    votes: index ? 4 : 6,
    percent: index ? 40 : 60,
  })),
  timeline: [{ at: now.toISOString(), responses: 10 }],
  generated_at: now.toISOString(),
  named_voters: [],
};

async function installMocks(page: Page) {
  const baseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100";
  await page.context().addCookies([
    {
      name: "utag_session",
      value: "isolated-poll-action-fixture",
      url: baseUrl,
      httpOnly: true,
    },
    {
      name: "utag_csrf",
      value: "isolated-poll-action-csrf-fixture",
      url: baseUrl,
    },
  ]);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/me") {
      await route.fulfill({
        json: {
          id: "191f6c4f-5f4e-4a45-8914-c2af48a9ef7b",
          full_name: "Dr. Ama Mensah",
          email: "poll-organizer@example.edu.gh",
          profile_media_id: null,
          must_change_password: false,
          must_complete_executive_profile: false,
          roles: ["executive"],
          permissions: [
            "dashboard.view",
            "polls.manage",
            "polls.results",
            "polls.export",
          ],
        },
      });
      return;
    }
    if (path === "/api/v1/notifications/unread-count") {
      await route.fulfill({ json: { unread: 0 } });
      return;
    }
    if (path === `/api/v1/polls/${pollId}/results`) {
      await route.fulfill({ json: results });
      return;
    }
    if (path === `/api/v1/polls/${pollId}`) {
      await route.fulfill({ json: poll });
      return;
    }
    if (path === "/api/v1/polls") {
      await route.fulfill({
        json: { items: [poll], page: 1, page_size: 20, total: 1, pages: 1 },
      });
      return;
    }
    await route.fulfill({ json: {} });
  });
}

async function expectActionsAboveNavigation(page: Page) {
  const panel = page.locator("[data-poll-organizer-panel]");
  const actions = page.locator("[data-poll-organizer-actions]");
  const navigation = page.locator("[data-dashboard-bottom-nav]");
  await panel.scrollIntoViewIfNeeded();
  await expect(panel).toBeVisible();
  await expect(actions).toBeVisible();
  await expect(navigation).toBeVisible();
  const [panelBox, navigationBox] = await Promise.all([
    panel.boundingBox(),
    navigation.boundingBox(),
  ]);
  expect(panelBox).not.toBeNull();
  expect(navigationBox).not.toBeNull();
  expect(panelBox!.y + panelBox!.height).toBeLessThanOrEqual(
    navigationBox!.y - 8,
  );
  const layout = await actions.evaluate((element) => ({
    actionsClientWidth: element.clientWidth,
    actionsScrollWidth: element.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    overflowX: getComputedStyle(element).overflowX,
  }));
  expect(
    layout.documentScrollWidth,
    JSON.stringify(layout),
  ).toBeLessThanOrEqual(layout.innerWidth);
}

test("organizer actions stay above compact navigation", async ({
  page,
}, testInfo) => {
  await installMocks(page);
  await page.setViewportSize({ width: 820, height: 900 });
  await page.goto(`/dashboard/polls/${pollId}`);

  const actions = page.locator("[data-poll-organizer-actions]");
  const panel = page.locator("[data-poll-organizer-panel]");
  await expectActionsAboveNavigation(page);
  expect(
    await panel.evaluate((element) => getComputedStyle(element).position),
  ).toBe("sticky");
  await page.screenshot({
    path: testInfo.outputPath("organizer-actions-tablet.png"),
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await expectActionsAboveNavigation(page);
  expect(
    await actions.evaluate((element) => getComputedStyle(element).flexWrap),
  ).toBe("nowrap");
  await page.screenshot({
    path: testInfo.outputPath("organizer-actions-mobile.png"),
  });
});
