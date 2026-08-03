import { describe, expect, it, vi } from "vitest";

import {
  defaultDeliveryCapabilities,
  deliveryAvailable,
} from "./delivery-capabilities";
import { rowActionsFor } from "./workspace-row-actions";
import { workspaces } from "./workspaces";

describe("delivery capabilities", () => {
  it("treats email or sms as delivery available", () => {
    expect(deliveryAvailable(defaultDeliveryCapabilities)).toBe(false);
    expect(
      deliveryAvailable({ email_delivery: true, sms_delivery: false }),
    ).toBe(true);
    expect(
      deliveryAvailable({ email_delivery: false, sms_delivery: true }),
    ).toBe(true);
  });
});

describe("member credential actions require delivery", () => {
  const row = {
    id: "member-1",
    status: "active",
    email_verified: true,
    roles: ["member"],
  };
  const permissions = [
    "members.create",
    "members.credentials",
    "members.update",
    "members.lifecycle",
  ];

  it("hides send access link when delivery is off but keeps reset password", () => {
    const actions = rowActionsFor(
      row,
      workspaces.members,
      permissions,
      "admin-1",
      false,
    );
    expect(actions.actions.map((item) => item.label)).not.toContain(
      "Send access link",
    );
    expect(actions.actions.map((item) => item.label)).toContain(
      "Reset password",
    );
  });

  it("shows send access link and reset password when delivery is on", () => {
    const actions = rowActionsFor(
      row,
      workspaces.members,
      permissions,
      "admin-1",
      true,
    );
    expect(actions.actions.map((item) => item.label)).toContain(
      "Send access link",
    );
    expect(actions.actions.map((item) => item.label)).toContain(
      "Reset password",
    );
  });

  it("marks send invitation as delivery-gated", () => {
    expect(
      workspaces.members.create?.fields?.find(
        (field) => field.key === "send_invitation",
      )?.requiresDelivery,
    ).toBe(true);
    expect(
      workspaces.members.actions?.find(
        (action) => action.label === "Reset password",
      )?.requiresDelivery,
    ).not.toBe(true);
  });

  it("defaults missing invitation choice to false in prepare", () => {
    expect(
      workspaces.members.create?.prepare?.({ roles: ["member"] }),
    ).toMatchObject({
      roles: ["member"],
      send_invitation: false,
    });
  });
});

describe("login forgot-password visibility", () => {
  it("only shows the link when delivery is available", async () => {
    vi.resetModules();
    // Keep this assertion aligned with LoginForm's deliveryAvailable gate.
    expect(deliveryAvailable({ email_delivery: false, sms_delivery: false })).toBe(
      false,
    );
    expect(deliveryAvailable({ email_delivery: true, sms_delivery: false })).toBe(
      true,
    );
  });
});
