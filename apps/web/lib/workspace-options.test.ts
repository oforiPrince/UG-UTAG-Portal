import { describe, expect, it } from "vitest";

import {
  documentAudiencesForCategory,
  nextMultiSelectValue,
  workspaceOptionQueryState,
} from "./workspace-options";
import { workspaces, workspaceFilterMatches } from "./workspaces";

describe("workspace option loading", () => {
  it("does not mark static choices as loading when their disabled query is pending", () => {
    expect(
      workspaceOptionQueryState(false, {
        isPending: true,
        isError: false,
      }),
    ).toEqual({ isLoading: false, isError: false });
  });

  it("reports loading and failures only for remote option sources", () => {
    expect(
      workspaceOptionQueryState(true, {
        isPending: true,
        isError: false,
      }),
    ).toEqual({ isLoading: true, isError: false });
    expect(
      workspaceOptionQueryState(true, {
        isPending: false,
        isError: true,
      }),
    ).toEqual({ isLoading: false, isError: true });
  });
});

describe("multiple workspace options", () => {
  it("adds General Public without removing protected audiences", () => {
    expect(
      nextMultiSelectValue(["member", "executive"], "general_public", true),
    ).toEqual(["member", "executive", "general_public"]);
  });

  it("adds a member role without removing General Public", () => {
    expect(nextMultiSelectValue(["general_public"], "member", true)).toEqual([
      "general_public",
      "member",
    ]);
  });

  it("does not duplicate an already selected audience", () => {
    expect(nextMultiSelectValue(["member"], "member", true)).toEqual([
      "member",
    ]);
  });
});

describe("document audience categories", () => {
  it("replaces a public-only selection when a document becomes internal", () => {
    expect(
      documentAudiencesForCategory("internal", ["general_public"]),
    ).toEqual(["member"]);
  });

  it("preserves protected audiences while removing public visibility", () => {
    expect(
      documentAudiencesForCategory("internal", ["general_public", "executive"]),
    ).toEqual(["executive"]);
  });

  it("allows public visibility for external documents", () => {
    expect(
      documentAudiencesForCategory("external", ["general_public"]),
    ).toEqual(["general_public"]);
  });

  it("preserves an intentionally empty protected audience", () => {
    expect(documentAudiencesForCategory("internal", [])).toEqual([]);
  });
});

describe("member creation", () => {
  it("keeps organization choices inside the selected hierarchy", () => {
    const fields = workspaces.members.create?.fields ?? [];
    const college = fields.find((field) => field.key === "college_id");
    const school = fields.find((field) => field.key === "school_id");
    const department = fields.find((field) => field.key === "department_id");

    expect(college?.clearOnChange).toEqual(["school_id", "department_id"]);
    expect(school?.clearOnChange).toEqual(["department_id"]);
    expect(
      school?.optionSource?.filterForValues?.(
        { id: "school-1", parent_id: "college-1" },
        { college_id: "college-1" },
      ),
    ).toBe(true);
    expect(
      school?.optionSource?.filterForValues?.(
        { id: "school-2", parent_id: "college-2" },
        { college_id: "college-1" },
      ),
    ).toBe(false);
    expect(
      department?.optionSource?.filterForValues?.(
        { id: "department-1", parent_id: "school-1" },
        { school_id: "school-1" },
      ),
    ).toBe(true);
  });

  it("shows only valid parents when an organization unit is managed", () => {
    const parent = workspaces.organization.create?.fields?.find(
      (field) => field.key === "parent_id",
    );
    expect(
      parent?.optionSource?.filterForValues?.(
        { unit_type: "college" },
        { unit_type: "school" },
      ),
    ).toBe(true);
    expect(
      parent?.optionSource?.filterForValues?.(
        { unit_type: "school" },
        { unit_type: "department" },
      ),
    ).toBe(true);
    expect(
      parent?.optionSource?.filterForValues?.(
        { unit_type: "department" },
        { unit_type: "school" },
      ),
    ).toBe(false);
  });

  it("uses create wording and preserves the explicit invitation choice", () => {
    const create = workspaces.members.create!;
    expect(create.label).toBe("Create member");
    expect(create.fields).toContainEqual(
      expect.objectContaining({
        key: "send_invitation",
        defaultValue: true,
        createOnly: true,
      }),
    );
    expect(
      create.prepare?.({ roles: ["member"], send_invitation: false }),
    ).toMatchObject({
      roles: ["member"],
      send_invitation: false,
    });
    expect(create.prepare?.({ roles: ["member"] })).toMatchObject({
      send_invitation: false,
    });
    expect(
      create.fields?.find((field) => field.key === "send_invitation")
        ?.requiresDelivery,
    ).toBe(true);
  });

  it("separates profile, lifecycle, credential, and role permissions", () => {
    expect(workspaces.members.create?.permission).toBe("members.create");
    expect(workspaces.members.update?.permission).toBe("members.update");
    expect(
      workspaces.members.update?.fields?.find((field) => field.key === "email"),
    ).toMatchObject({
      type: "email",
      required: true,
    });
    expect(
      workspaces.members.update?.fields?.find((field) => field.key === "email")
        ?.createOnly,
    ).not.toBe(true);
    expect(workspaces.members.delete?.permission).toBe("records.delete");
    expect(workspaces.members.delete?.excludeSelf).toBe(true);
    expect(
      workspaces.members.create?.fields?.find((field) => field.key === "roles")
        ?.permission,
    ).toBe("members.roles");
    expect(workspaces.members.actions?.map((action) => action.label)).toEqual([
      "Manage extra access",
      "Send access link",
      "Reset password",
      "Sign out all devices",
      "Deactivate member",
      "Reactivate member",
    ]);
    expect(workspaces.members.actions?.[0]).toMatchObject({
      permission: "members.permissions",
      method: "PUT",
      fields: [
        expect.objectContaining({
          key: "extra_permissions",
          type: "multiselect",
          optionSource: expect.any(Object),
        }),
      ],
    });
    expect(
      workspaces.members.actions?.[0]?.prepare?.({
        extra_permissions: ["content.edit", "media.manage"],
      }),
    ).toEqual({
      permissions: ["content.edit", "media.manage"],
    });
  });

  it("uses one member workspace and filters multi-role accounts correctly", () => {
    expect(workspaces.administrators).toBeUndefined();
    expect(workspaces.members.filters).toContainEqual(
      expect.objectContaining({
        key: "roles",
        options: expect.arrayContaining(["member", "administrator"]),
      }),
    );
    expect(
      workspaceFilterMatches(["member", "administrator"], "administrator"),
    ).toBe(true);
    expect(workspaceFilterMatches(["member", "editor"], "administrator")).toBe(
      false,
    );
  });

  it("uses related-record lookups instead of raw IDs for advertising orders", () => {
    const fields = workspaces["advert-orders"].create?.fields ?? [];
    for (const key of ["advertiser_id", "plan_id", "campaign_id"]) {
      expect(fields.find((field) => field.key === key)).toMatchObject({
        type: "select",
        optionSource: expect.any(Object),
      });
    }
    expect(
      fields.find((field) => field.key === "advertiser_id")?.optionSource,
    ).toMatchObject({
      endpoint: "/api/v1/adverts/advertisers",
    });
  });
});
