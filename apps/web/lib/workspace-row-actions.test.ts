import { describe, expect, it } from "vitest";

import {
  inlineRowMutations,
  overflowRowItems,
  rowActionsFor,
} from "./workspace-row-actions";
import { workspaces } from "./workspaces";

describe("rowActionsFor", () => {
  const eventRow = {
    id: "event-1",
    title: "Workshop",
    registration_required: true,
    registered: false,
    publication_status: "published",
  };

  it("gives members register but not edit on events", () => {
    const actions = rowActionsFor(eventRow, workspaces.events, [
      "dashboard.view",
    ]);
    expect(actions.canUpdate).toBe(false);
    expect(actions.canArchive).toBe(false);
    expect(actions.primary.map((item) => item.label)).toContain("Register");
    expect(actions.primary.map((item) => item.label)).not.toContain(
      "Cancel registration",
    );
  });

  it("shows cancel registration when already registered", () => {
    const actions = rowActionsFor(
      { ...eventRow, registered: true },
      workspaces.events,
      ["dashboard.view"],
    );
    expect(actions.secondary.map((item) => item.label)).toContain(
      "Cancel registration",
    );
  });

  it("hides self-targeted member lifecycle actions", () => {
    const actions = rowActionsFor(
      {
        id: "user-1",
        status: "active",
        email_verified: true,
        roles: ["member"],
      },
      workspaces.members,
      [
        "members.update",
        "members.lifecycle",
        "members.credentials",
        "members.permissions",
      ],
      "user-1",
    );
    expect(actions.canArchive).toBe(false);
    expect(
      actions.actions.some((item) => item.label === "Reset password"),
    ).toBe(false);
  });

  it("puts edit and archive into overflow for managers", () => {
    const actions = rowActionsFor(eventRow, workspaces.events, [
      "dashboard.view",
      "events.manage",
    ]);
    expect(actions.canUpdate).toBe(true);
    const overflow = overflowRowItems(actions);
    expect(overflow.some((item) => item.kind === "update")).toBe(true);
    expect(overflow.some((item) => item.kind === "archive")).toBe(true);
    expect(inlineRowMutations(actions).map((item) => item.label)).toContain(
      "Register",
    );
  });

  it("surfaces End appointment for executives.manage, not viewers", () => {
    const row = {
      id: "exec-1",
      is_active: true,
      member_name: "Ada",
      position_title: "President",
    };
    const viewer = rowActionsFor(row, workspaces.executives, [
      "dashboard.view",
      "executives.view",
    ]);
    expect(viewer.canArchive).toBe(false);

    const manager = rowActionsFor(row, workspaces.executives, [
      "dashboard.view",
      "executives.manage",
    ]);
    expect(manager.canArchive).toBe(true);
    expect(manager.archive?.label).toBe("End appointment");
    expect(manager.archive?.permission).toBe("executives.manage");
    expect(
      overflowRowItems(manager).some(
        (item) =>
          item.kind === "archive" && item.mutation.label === "End appointment",
      ),
    ).toBe(true);
  });

  it("surfaces Archive announcement for content.publish", () => {
    const row = {
      id: "ann-1",
      status: "published",
      title: "Notice",
      version: 1,
    };
    const viewer = rowActionsFor(row, workspaces.announcements, [
      "dashboard.view",
      "content.view",
    ]);
    expect(viewer.canArchive).toBe(false);

    const publisher = rowActionsFor(row, workspaces.announcements, [
      "dashboard.view",
      "content.publish",
    ]);
    expect(publisher.canArchive).toBe(true);
    expect(publisher.archive?.label).toBe("Archive announcement");
    expect(publisher.archive?.permission).toBe("content.publish");
  });

  it("keeps analytics view-only", () => {
    const actions = rowActionsFor(
      { id: "m1", key: "members", value: 12 },
      workspaces.analytics,
      ["analytics.view"],
    );
    expect(actions.primary).toEqual([]);
    expect(actions.secondary).toEqual([]);
    expect(actions.canUpdate).toBe(false);
  });
});
