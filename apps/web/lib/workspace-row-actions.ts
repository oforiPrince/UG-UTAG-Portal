import type {
  WorkspaceConfig,
  WorkspaceMutation,
  WorkspaceRow,
} from "@/lib/workspaces";

export function partitionDetailActions(actions: WorkspaceMutation[]) {
  const primary: WorkspaceMutation[] = [];
  const secondary: WorkspaceMutation[] = [];
  for (const action of actions) {
    if (
      action.openMode === "panel" ||
      (!action.danger &&
        !action.fields?.length &&
        !action.open &&
        action.openMode !== "tab")
    ) {
      primary.push(action);
    } else {
      secondary.push(action);
    }
  }
  return { primary, secondary };
}

export type RowActionSet = {
  canView: true;
  canUpdate: boolean;
  canDelete: boolean;
  update?: WorkspaceMutation;
  delete?: WorkspaceMutation;
  primary: WorkspaceMutation[];
  secondary: WorkspaceMutation[];
  /** All gated custom actions (before primary/secondary split). */
  actions: WorkspaceMutation[];
};

function mutationAllowed(
  mutation: WorkspaceMutation,
  row: WorkspaceRow,
  permissions: string[],
  currentUserId?: string,
  deliveryAvailable = true,
) {
  if (mutation.requiresDelivery && !deliveryAvailable) return false;
  if (!permissions.includes(mutation.permission)) return false;
  if (mutation.excludeSelf && currentUserId && row.id === currentUserId) {
    return false;
  }
  if (mutation.when && !mutation.when(row, permissions)) return false;
  return true;
}

export function rowActionsFor(
  row: WorkspaceRow,
  config: WorkspaceConfig,
  permissions: string[],
  currentUserId?: string,
  deliveryAvailable = true,
): RowActionSet {
  const update =
    config.update &&
    mutationAllowed(
      config.update,
      row,
      permissions,
      currentUserId,
      deliveryAvailable,
    )
      ? config.update
      : undefined;
  const deleteMutation =
    config.delete &&
    mutationAllowed(
      config.delete,
      row,
      permissions,
      currentUserId,
      deliveryAvailable,
    )
      ? config.delete
      : undefined;
  const actions = (config.actions ?? []).filter((item) =>
    mutationAllowed(item, row, permissions, currentUserId, deliveryAvailable),
  );
  const { primary, secondary } = partitionDetailActions(actions);

  return {
    canView: true,
    canUpdate: Boolean(update),
    canDelete: Boolean(deleteMutation),
    update,
    delete: deleteMutation,
    primary,
    secondary,
    actions,
  };
}

/** Buttons shown inline on the row (besides View). Rest go in overflow. */
export function inlineRowMutations(actions: RowActionSet): WorkspaceMutation[] {
  return actions.primary.slice(0, 2);
}

export function overflowRowItems(
  actions: RowActionSet,
): Array<
  | { kind: "mutation"; mutation: WorkspaceMutation }
  | { kind: "update"; mutation: WorkspaceMutation }
  | { kind: "delete"; mutation: WorkspaceMutation }
> {
  const inline = new Set(inlineRowMutations(actions));
  const items: Array<
    | { kind: "mutation"; mutation: WorkspaceMutation }
    | { kind: "update"; mutation: WorkspaceMutation }
    | { kind: "delete"; mutation: WorkspaceMutation }
  > = [];

  for (const mutation of actions.primary) {
    if (!inline.has(mutation)) {
      items.push({ kind: "mutation", mutation });
    }
  }
  for (const mutation of actions.secondary) {
    items.push({ kind: "mutation", mutation });
  }
  if (actions.update) {
    items.push({ kind: "update", mutation: actions.update });
  }
  if (actions.delete) {
    items.push({ kind: "delete", mutation: actions.delete });
  }
  return items;
}
