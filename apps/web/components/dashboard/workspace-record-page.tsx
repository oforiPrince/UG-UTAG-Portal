"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Inbox, LoaderCircle, RefreshCw, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import {
  MutationForm,
  ValueDisplay,
  endpointFor,
  recordImages,
} from "@/components/dashboard/workspace-client";
import { RecordDetailsView } from "@/components/dashboard/record-details-view";
import { Button } from "@/components/ui/button";
import {
  ConfirmDialog,
  type ConfirmDialogState,
} from "@/components/ui/confirm-dialog";
import { API_URL, api } from "@/lib/api";
import {
  defaultDeliveryCapabilities,
  deliveryAvailable,
} from "@/lib/delivery-capabilities";
import { display } from "@/lib/workspace-display";
import { visibleDetailEntries } from "@/lib/workspace-detail";
import { rowActionsFor } from "@/lib/workspace-row-actions";
import { workspacePresentations } from "@/lib/workspace-presentation";
import {
  workspaces,
  type WorkspaceMutation,
  type WorkspaceRow,
} from "@/lib/workspaces";
import { formatPersonName } from "@/lib/utils";

type User = { id: string; permissions: string[] };

function safeReturnTo(value: string | null, fallback: string) {
  if (!value?.startsWith("/dashboard")) return fallback;
  if (value.startsWith("//") || value.includes("://")) return fallback;
  return value;
}

function recordTitle(row: WorkspaceRow, key: string) {
  const value = display(row[key], key);
  return key === "full_name" ? formatPersonName(value) : value;
}

export function WorkspaceRecordPage({
  configKey,
  mode,
  recordId,
}: {
  configKey: string;
  mode: "details" | "create" | "edit";
  recordId?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const config = workspaces[configKey];
  const presentation = workspacePresentations[configKey];
  const [taskMutation, setTaskMutation] = useState<WorkspaceMutation>();
  const [confirmation, setConfirmation] = useState<
    (ConfirmDialogState & { mutation: WorkspaceMutation }) | null
  >(null);

  const backHref = safeReturnTo(
    searchParams.get("returnTo"),
    presentation?.listHref ?? "/dashboard",
  );
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
    staleTime: 60_000,
  });
  const capabilities = useQuery({
    queryKey: ["public", "capabilities"],
    queryFn: () =>
      api<typeof defaultDeliveryCapabilities>("/api/v1/public/capabilities"),
    staleTime: 60_000,
    placeholderData: defaultDeliveryCapabilities,
  });
  const record = useQuery({
    queryKey: [config?.queryKey, "record", recordId],
    queryFn: () => {
      if (!presentation?.detailEndpoint || !recordId) {
        throw new Error("This record page is not configured");
      }
      return api<WorkspaceRow>(presentation.detailEndpoint(recordId));
    },
    enabled:
      mode !== "create" && Boolean(presentation?.detailEndpoint && recordId),
  });
  const action = useMutation({
    mutationFn: ({
      mutation,
      row,
    }: {
      mutation: WorkspaceMutation;
      row: WorkspaceRow;
    }) =>
      api(endpointFor(mutation, row), {
        method: mutation.method ?? "POST",
        headers: mutation.headers ? mutation.headers(row) : undefined,
      }),
    onSuccess: async (result, variables) => {
      const message =
        result &&
        typeof result === "object" &&
        "message" in result &&
        typeof (result as { message: unknown }).message === "string"
          ? (result as { message: string }).message
          : variables.mutation.successMessage;
      toast.success(message);
      setConfirmation(null);
      await queryClient.invalidateQueries({ queryKey: [config.queryKey] });
      if (variables.mutation === config.delete) {
        router.replace(backHref);
      } else {
        await record.refetch();
      }
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Action failed"),
  });

  const permissions = useMemo(
    () => user.data?.permissions ?? [],
    [user.data?.permissions],
  );
  const canUseMutation = (mutation?: WorkspaceMutation) =>
    Boolean(mutation && permissions.includes(mutation.permission));
  const mutation = mode === "create" ? config?.create : config?.update;
  const wizardSteps =
    mode === "create" ? presentation?.createSteps : presentation?.editSteps;
  const draftKey = `workspace-draft:${configKey}:${mode}:${recordId ?? "new"}`;

  const details = useMemo(() => {
    if (!record.data || !config.detail) return [];
    return visibleDetailEntries(record.data, config.detail, permissions).map(
      ({ field, value }) => ({
        key: field.key,
        label: field.label,
        value,
        richtext: field.format === "richtext",
        format: field.format,
      }),
    );
  }, [config.detail, permissions, record.data]);

  if (!config || !presentation?.fullPage) {
    return (
      <div className="workspace-folio mx-auto grid max-w-xl place-items-center rounded-[1.6rem] p-10 text-center sm:p-12">
        <span className="grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
          <Inbox className="size-5" />
        </span>
        <h2 className="display-type mt-5 text-2xl">Page unavailable</h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          This record page is not part of the operator workspace.
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard">Return to dashboard</Link>
        </Button>
      </div>
    );
  }

  if (!canUseMutation(mutation) && mode !== "details" && !user.isLoading) {
    return (
      <div className="workspace-folio mx-auto grid max-w-xl place-items-center rounded-[1.6rem] p-10 text-center sm:p-12">
        <h2 className="display-type text-2xl">Editing is not available</h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Your account does not have permission to change this{" "}
          {config.detail?.noun.toLowerCase() ?? "record"}.
        </p>
        <Button asChild className="mt-6" variant="outline">
          <Link href={backHref}>Return to {config.title}</Link>
        </Button>
      </div>
    );
  }

  if (user.isLoading || (mode !== "create" && record.isLoading)) {
    return (
      <div
        className="workspace-folio grid min-h-[28rem] place-items-center rounded-[1.6rem]"
        aria-label={`Loading ${config.detail?.noun.toLowerCase() ?? "item"}`}
      >
        <span className="grid justify-items-center gap-3 text-sm text-muted">
          <LoaderCircle className="size-6 animate-spin text-coral" />
          Loading {config.detail?.noun.toLowerCase() ?? "item"}…
        </span>
      </div>
    );
  }

  if (mode !== "create" && (record.error || !record.data)) {
    return (
      <div className="workspace-folio mx-auto grid max-w-xl place-items-center rounded-[1.6rem] p-10 text-center sm:p-12">
        <span className="grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
          <Inbox className="size-5" />
        </span>
        <h2 className="display-type mt-5 text-2xl">
          This {config.detail?.noun.toLowerCase() ?? "item"} could not be loaded
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          It may have been removed, or your account may no longer have access.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button variant="outline" onClick={() => record.refetch()}>
            <RefreshCw className="size-4" /> Try again
          </Button>
          <Button asChild>
            <Link href={backHref}>Return to list</Link>
          </Button>
        </div>
      </div>
    );
  }

  const handleSaved = (saved: WorkspaceRow) => {
    const id = String(saved.id ?? recordId ?? "");
    if (!id) {
      router.replace(backHref);
      return;
    }
    const href =
      presentation.detailHref?.(saved) ?? `${presentation.listHref}/${id}`;
    router.replace(`${href}?returnTo=${encodeURIComponent(backHref)}`);
  };

  if (mode === "create" || mode === "edit") {
    if (!mutation) return null;
    return (
      <div className="grid gap-5">
        <MutationForm
          config={config}
          mutation={mutation}
          mode={mode}
          row={mode === "edit" ? record.data : undefined}
          permissions={permissions}
          deliveryAvailable={deliveryAvailable(
            capabilities.data ?? defaultDeliveryCapabilities,
          )}
          steps={wizardSteps}
          variant="page"
          draftKey={draftKey}
          recoverableFields={presentation.recoverableFields}
          showCloseButton={false}
          cancelLabel={mode === "edit" ? "Back to details" : "Cancel"}
          close={() =>
            router.push(
              mode === "edit" && record.data
                ? `${presentation.detailHref?.(record.data) ?? backHref}?returnTo=${encodeURIComponent(backHref)}`
                : backHref,
            )
          }
          onSaved={handleSaved}
        />
      </div>
    );
  }

  const row = record.data!;
  const rowActions = rowActionsFor(
    row,
    config,
    permissions,
    user.data?.id,
    deliveryAvailable(capabilities.data ?? defaultDeliveryCapabilities),
  );

  function runMutation(next: WorkspaceMutation) {
    if (next.fields?.length) {
      setTaskMutation(next);
      return;
    }
    if (next.open || next.openMode === "tab") {
      window.open(
        next.href ? next.href(row) : `${API_URL}${endpointFor(next, row)}`,
        "_blank",
        "noopener,noreferrer",
      );
      return;
    }
    if (next.openMode === "panel" && next.href) {
      router.push(next.href(row));
      return;
    }
    if (next.confirm) {
      setConfirmation({
        mutation: next,
        title: next.label,
        description: next.confirm,
        confirmLabel: next.label,
        danger: next.danger,
      });
      return;
    }
    action.mutate({ mutation: next, row });
  }

  return (
    <div className="mx-auto grid w-full max-w-5xl gap-6">
      <Button
        asChild
        variant="ghost"
        className="w-fit px-1 text-xs text-muted hover:bg-transparent hover:text-ink"
      >
        <Link href={backHref}>
          <ArrowLeft className="size-4" /> Back to {config.title}
        </Link>
      </Button>
      <RecordDetailsView
        noun={config.detail?.noun ?? "Record"}
        title={recordTitle(
          row,
          config.detail?.titleKey ?? config.columns[0]?.key ?? "title",
        )}
        subtitle={config.detail?.subtitleKeys
          ?.map((key) => display(row[key], key))
          .filter((value) => value !== "Not provided")
          .join(" · ")}
        images={recordImages(row)}
        heroShape={row.profile_media_id ? "portrait" : "landscape"}
        entries={details}
        sections={presentation.detailSections}
        variant="page"
        primaryActions={rowActions.primary}
        secondaryActions={rowActions.secondary}
        canUpdate={rowActions.canUpdate}
        canDelete={rowActions.canDelete}
        updateLabel={rowActions.update?.label}
        deleteLabel={rowActions.delete?.label}
        actionPending={action.isPending}
        onPrimaryAction={runMutation}
        onEdit={() => {
          const href = presentation.editHref?.(row);
          if (href)
            router.push(`${href}?returnTo=${encodeURIComponent(backHref)}`);
        }}
        onDelete={() => rowActions.delete && runMutation(rowActions.delete)}
        ValueDisplay={ValueDisplay}
      />

      {taskMutation ? (
        <div
          className="fixed inset-0 z-[90] grid place-items-center bg-ink/20 p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget)
              setTaskMutation(undefined);
          }}
          role="presentation"
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-label={taskMutation.label}
            className="max-h-[min(46rem,calc(100dvh-2rem))] w-full max-w-2xl overflow-y-auto rounded-[1.5rem] border border-line bg-paper p-6 shadow-2xl sm:p-8"
          >
            <div className="flex justify-end">
              <Button
                size="icon"
                variant="ghost"
                aria-label="Close task"
                onClick={() => setTaskMutation(undefined)}
              >
                <X className="size-4" />
              </Button>
            </div>
            <MutationForm
              config={config}
              mutation={taskMutation}
              mode="edit"
              row={row}
              permissions={permissions}
              deliveryAvailable={deliveryAvailable(
                capabilities.data ?? defaultDeliveryCapabilities,
              )}
              showCloseButton={false}
              close={() => setTaskMutation(undefined)}
              onSaved={() => {
                setTaskMutation(undefined);
                void record.refetch();
              }}
            />
          </section>
        </div>
      ) : null}

      <ConfirmDialog
        open={Boolean(confirmation)}
        title={confirmation?.title ?? "Confirm action"}
        description={confirmation?.description ?? "Confirm this action."}
        confirmLabel={confirmation?.confirmLabel}
        danger={confirmation?.danger}
        busy={action.isPending}
        onCancel={() => setConfirmation(null)}
        onConfirm={() => {
          if (confirmation)
            action.mutate({ mutation: confirmation.mutation, row });
        }}
      />
    </div>
  );
}
