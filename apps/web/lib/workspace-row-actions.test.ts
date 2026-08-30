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
    expect(actions.canDelete).toBe(false);
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
    expect(actions.canDelete).toBe(false);
    expect(
      actions.actions.some((item) => item.label === "Reset password"),
    ).toBe(false);
  });

  it("puts edit and administrator-only delete into overflow", () => {
    const actions = rowActionsFor(eventRow, workspaces.events, [
      "dashboard.view",
      "events.manage",
      "records.delete",
    ]);
    expect(actions.canUpdate).toBe(true);
    const overflow = overflowRowItems(actions);
    expect(overflow.some((item) => item.kind === "update")).toBe(true);
    expect(overflow.some((item) => item.kind === "delete")).toBe(true);
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
    expect(viewer.canDelete).toBe(false);

    const manager = rowActionsFor(row, workspaces.executives, [
      "dashboard.view",
      "executives.manage",
    ]);
    expect(manager.canDelete).toBe(false);
    expect(manager.actions.map((item) => item.label)).toContain(
      "End appointment",
    );

    const administrator = rowActionsFor(row, workspaces.executives, [
      "dashboard.view",
      "executives.manage",
      "records.delete",
    ]);
    expect(administrator.canDelete).toBe(true);
    expect(administrator.delete?.label).toBe("Delete appointment");
    expect(administrator.delete?.permission).toBe("records.delete");
    expect(
      overflowRowItems(administrator).some(
        (item) =>
          item.kind === "delete" &&
          item.mutation.label === "Delete appointment",
      ),
    ).toBe(true);
  });

  it("keeps permanent announcement deletion administrator-only", () => {
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
    expect(viewer.canDelete).toBe(false);

    const publisher = rowActionsFor(row, workspaces.announcements, [
      "dashboard.view",
      "content.publish",
    ]);
    expect(publisher.canDelete).toBe(false);

    const administrator = rowActionsFor(row, workspaces.announcements, [
      "dashboard.view",
      "content.publish",
      "records.delete",
    ]);
    expect(administrator.canDelete).toBe(true);
    expect(administrator.delete?.label).toBe("Delete announcement");
    expect(administrator.delete?.permission).toBe("records.delete");
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
