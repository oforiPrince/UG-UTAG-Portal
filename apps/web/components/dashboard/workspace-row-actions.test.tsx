import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkspaceRowActions } from "@/components/dashboard/workspace-row-actions";
import type { RowActionSet } from "@/lib/workspace-row-actions";
import type { WorkspaceMutation } from "@/lib/workspaces";

afterEach(cleanup);

const mutation = (
  label: string,
  extra: Partial<WorkspaceMutation> = {},
): WorkspaceMutation => ({
  label,
  permission: "members.update",
  endpoint: "/api/v1/members/1",
  successMessage: label,
  ...extra,
});

const actions: RowActionSet = {
  canView: true,
  canUpdate: true,
  canDelete: true,
  update: mutation("Edit member"),
  delete: mutation("Delete member", { danger: true }),
  primary: [
    mutation("Reset password"),
    mutation("Sign out all devices"),
  ],
  secondary: [mutation("Deactivate member", { danger: true })],
  actions: [],
};

function renderActions(overrides: Partial<RowActionSet> = {}) {
  const onView = vi.fn();
  const onMutation = vi.fn();
  const onEdit = vi.fn();
  const onDelete = vi.fn();
  render(
    <WorkspaceRowActions
      compact
      actions={{ ...actions, ...overrides }}
      onView={onView}
      onMutation={onMutation}
      onEdit={onEdit}
      onDelete={onDelete}
    />,
  );
  return { onView, onMutation, onEdit, onDelete };
}

describe("WorkspaceRowActions", () => {
  it("shows an icon-only View control and hides mutation labels until overflow opens", () => {
    const { onView, onMutation } = renderActions();

    const view = screen.getByRole("button", { name: "View" });
    expect(view.textContent).toBe("");
    expect(view.getAttribute("aria-label")).toBe("View");
    expect(screen.queryByText("Reset password")).toBeNull();
    expect(screen.queryByText("Sign out all devices")).toBeNull();
    expect(screen.queryByText("Deactivate member")).toBeNull();

    fireEvent.click(view);
    expect(onView).toHaveBeenCalledTimes(1);

    const overflow = screen.getByRole("button", { name: "More actions" });
    expect(overflow.getAttribute("aria-haspopup")).toBe("menu");
    fireEvent.click(overflow);
    expect(screen.getByRole("menu", { name: "Row actions" })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "Reset password" }));
    expect(onMutation).toHaveBeenCalledWith(actions.primary[0]);
  });

  it("keeps edit and delete available from the overflow menu", () => {
    const { onEdit, onDelete } = renderActions();

    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Edit member" }));
    expect(onEdit).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete member" }));
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("omits the overflow trigger when a row has no mutations", () => {
    renderActions({
      canUpdate: false,
      canDelete: false,
      update: undefined,
      delete: undefined,
      primary: [],
      secondary: [],
    });

    expect(screen.getByRole("button", { name: "View" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "More actions" })).toBeNull();
  });
});
