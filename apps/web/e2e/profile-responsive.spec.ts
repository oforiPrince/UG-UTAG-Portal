import { expect, test, type Page } from "@playwright/test";

async function installProfileMocks(page: Page) {
  const baseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100";
  await page.context().addCookies([
    {
      name: "utag_session",
      value: "isolated-profile-browser-fixture",
      url: baseUrl,
      httpOnly: true,
    },
    {
      name: "utag_csrf",
      value: "isolated-profile-csrf-fixture",
      url: baseUrl,
    },
  ]);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/me") {
      await route.fulfill({
        json: {
          id: "191f6c4f-5f4e-4a45-8914-c2af48a9ef7b",
          full_name: "Dr. Kwame Ofori",
          email: "kwame@example.edu.gh",
          profile_media_id: null,
          staff_id: "UTAG-006",
          title: "Dr.",
          other_name: "Kwame",
          surname: "Ofori",
          gender: "Male",
          academic_rank: "Associate Professor",
          phone_number: "+233 20 555 0106",
          school_id: "school-1",
          college_id: "college-1",
          department_id: "department-1",
          must_change_password: false,
          must_complete_executive_profile: false,
          roles: ["administrator"],
          permissions: ["dashboard.view", "settings.manage"],
        },
      });
      return;
    }
    if (path === "/api/v1/auth/executive-profile") {
      await route.fulfill({ json: null });
      return;
    }
    if (path === "/api/v1/organization/units") {
      await route.fulfill({
        json: [
          {
            id: "college-1",
            name: "College of Humanities",
            unit_type: "college",
            parent_id: null,
            is_active: true,
          },
          {
            id: "school-1",
            name: "School of Languages",
            unit_type: "school",
            parent_id: "college-1",
            is_active: true,
          },
          {
            id: "department-1",
            name: "Department of African and Asian Languages",
            unit_type: "department",
            parent_id: "school-1",
            is_active: true,
          },
        ],
      });
      return;
    }
    if (path === "/api/v1/notifications/unread-count") {
      await route.fulfill({ json: { unread: 0 } });
      return;
    }
    if (path === "/api/v1/polls") {
      await route.fulfill({
        json: { items: [], page: 1, page_size: 20, total: 0, pages: 1 },
      });
      return;
    }
    await route.fulfill({ json: {} });
  });
}

async function expectActionAboveNavigation(page: Page) {
  const save = page.getByRole("button", { name: "Save account" });
  const actionDock = save.locator("..");
  const department = page.getByLabel("DEPARTMENT");
  const navigation = page.locator("[data-dashboard-bottom-nav]");
  await save.scrollIntoViewIfNeeded();
  await expect(save).toBeVisible();
  await expect(navigation).toBeVisible();
  const [saveBox, actionDockBox, departmentBox, navigationBox] =
    await Promise.all([
      save.boundingBox(),
      actionDock.boundingBox(),
      department.boundingBox(),
      navigation.boundingBox(),
    ]);
  expect(saveBox).not.toBeNull();
  expect(actionDockBox).not.toBeNull();
  expect(departmentBox).not.toBeNull();
  expect(navigationBox).not.toBeNull();
  expect(departmentBox!.y + departmentBox!.height).toBeLessThanOrEqual(
    actionDockBox!.y - 8,
  );
  expect(saveBox!.y + saveBox!.height).toBeLessThanOrEqual(
    navigationBox!.y - 8,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);

  await page.getByLabel("DEPARTMENT").focus();
  await page.keyboard.press("Tab");
  await expect(save).toBeFocused();
}

test("profile actions stay above dashboard navigation on tablet and mobile", async ({
  page,
}, testInfo) => {
  await installProfileMocks(page);
  await page.setViewportSize({ width: 820, height: 900 });
  await page.goto("/dashboard/profile");
  await expect(
    page.getByText("Name and contact details", { exact: true }),
  ).toBeVisible();
  await expectActionAboveNavigation(page);
  await page.screenshot({
    path: testInfo.outputPath("profile-actions-tablet.png"),
    fullPage: false,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await expectActionAboveNavigation(page);
  await page.screenshot({
    path: testInfo.outputPath("profile-actions-mobile.png"),
    fullPage: false,
  });
});
