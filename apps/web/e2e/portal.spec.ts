import { expect, test } from "@playwright/test";

test("public portal renders with the institutional font stack", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("main")).toBeVisible();
  await expect(page.getByRole("link", { name: "Member login" })).toBeVisible();
  const fontFamily = await page
    .locator("body")
    .evaluate((element) => window.getComputedStyle(element).fontFamily);
  expect(fontFamily).toContain("Inter");

  const faviconHref = await page
    .locator('link[rel="icon"]')
    .first()
    .getAttribute("href");
  expect(faviconHref).toBeTruthy();
  const faviconResponse = await page.request.get(faviconHref!);
  expect(faviconResponse.ok()).toBe(true);
  expect(faviconResponse.headers()["content-type"]).toMatch(/^image\//);
});

test("public website routes render without browser errors", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));

  for (const route of [
    "/about",
    "/leadership",
    "/news",
    "/events",
    "/resources",
    "/gallery",
    "/contact",
    "/search",
    "/login",
  ]) {
    const response = await page.goto(route);
    expect(response?.ok(), `${route} returned ${response?.status()}`).toBe(true);
    await expect(page.locator("main")).toBeVisible();
  }

  expect(browserErrors).toEqual([]);
});

test("public navigation works at a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Mobile navigation" })
    .getByRole("link", { name: "About us", exact: true })
    .click();
  await expect(page).toHaveURL(/\/about$/);
});

test("protected dashboard redirects unauthenticated visitors", async ({
  page,
}) => {
  await page.goto("/dashboard/members");
  await expect(page).toHaveURL(/\/login\?next=%2Fdashboard%2Fmembers/);
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
});

test("contact form exposes validation errors before submission", async ({
  page,
}) => {
  await page.goto("/contact");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("Enter your name")).toBeVisible();
  await expect(page.getByText("Enter a valid email address")).toBeVisible();
  await expect(
    page.getByText("Enter a subject using at least 3 characters"),
  ).toBeVisible();
  await expect(
    page.getByText("Enter a message using at least 10 characters"),
  ).toBeVisible();
});

test("configured member credentials can complete sign in", async ({ page }) => {
  const email = process.env.E2E_MEMBER_EMAIL;
  const password = process.env.E2E_MEMBER_PASSWORD;
  test.skip(
    !email || !password,
    "Set E2E member credentials for the live-stack journey",
  );

  await page.goto("/login");
  await page.getByLabel("University or member email").fill(email!);
  await page.locator('input[name="password"]').fill(password!);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByText("Member workspace")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  const mobileSidebar = page.locator("aside:visible");
  await expect(mobileSidebar.getByRole("button", { name: "Sign out" })).toBeVisible();
  await mobileSidebar.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
});
