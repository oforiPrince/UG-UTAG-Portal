"use client";

import {
  Archive,
  LoaderCircle,
  Pencil,
  X,
} from "lucide-react";
import Image from "next/image";
import type { ComponentType } from "react";

import { WorkspaceRichTextValue } from "@/components/dashboard/workspace-rich-text-value";
import { Button } from "@/components/ui/button";
import { display, displayChoice } from "@/lib/workspace-display";
import type { WorkspaceDetailField } from "@/lib/workspace-detail";
import type { WorkspaceMutation } from "@/lib/workspaces";
import { cn, humanize } from "@/lib/utils";

export { partitionDetailActions } from "@/lib/workspace-row-actions";

type DetailEntry = {
  key: string;
  label: string;
  value: unknown;
  richtext?: boolean;
  format?: WorkspaceDetailField["format"];
};

type RecordImage = {
  id: string;
  name: string;
  alt: string;
};

type ValueDisplayComponent = ComponentType<{
  value: unknown;
  fieldKey: string;
  compact?: boolean;
}>;

const CHIP_KEYS = new Set([
  "status",
  "event_type",
  "category",
  "priority",
  "publication_status",
  "outcome",
  "payment_status",
  "fulfilment",
]);

const SPOTLIGHT_KEYS = new Set([
  "when",
  "venue",
  "address",
  "document_date",
  "published_at",
  "starts_at",
  "ends_at",
  "public_id",
  "email",
  "phone_number",
  "position",
  "portfolio",
  "academic_rank",
  "unit_type",
  "parent_name",
  "placement_name",
  "advertiser_name",
]);

const PROSE_KEYS = new Set([
  "short_description",
  "description_html",
  "description",
  "content_html",
  "excerpt",
  "summary",
  "biography_html",
  "notes",
  "error_message",
]);

function statusTone(value: unknown) {
  const status = String(value).toLowerCase();
  if (
    [
      "active",
      "published",
      "ready",
      "success",
      "completed",
      "paid",
      "upcoming",
      "ongoing",
      "true",
    ].includes(status)
  ) {
    return "bg-emerald-500/12 text-emerald-800 dark:text-emerald-300";
  }
  if (
    [
      "urgent",
      "rejected",
      "failed",
      "suspended",
      "cancelled",
      "archived",
      "false",
    ].includes(status)
  ) {
    return "bg-red-500/12 text-red-700 dark:text-red-300";
  }
  if (
    ["draft", "queued", "scanning", "pending", "invited", "review"].includes(
      status,
    )
  ) {
    return "bg-gold/18 text-ink";
  }
  return "bg-ink/6 text-ink/80";
}

function formatPlain(value: unknown, key: string) {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" || typeof value === "number") {
    return displayChoice(value, key);
  }
  return display(value, key);
}

function ValueNode({
  entry,
  ValueDisplay,
  prose = false,
}: {
  entry: DetailEntry;
  ValueDisplay: ValueDisplayComponent;
  prose?: boolean;
}) {
  if (entry.richtext && typeof entry.value === "string") {
    return (
      <div className={prose ? "[&_.rich-text-content]:text-sm [&_.rich-text-content]:leading-7" : undefined}>
        <WorkspaceRichTextValue html={entry.value} />
      </div>
    );
  }
  if (prose && (typeof entry.value === "string" || typeof entry.value === "number")) {
    return (
      <p className="text-sm leading-7 whitespace-pre-wrap text-ink">
        {formatPlain(entry.value, entry.key)}
      </p>
    );
  }
  return <ValueDisplay value={entry.value} fieldKey={entry.key} />;
}

export function RecordDetailsView({
  noun,
  title,
  subtitle,
  images,
  entries,
  primaryActions,
  secondaryActions,
  canUpdate,
  canArchive,
  updateLabel,
  archiveLabel,
  actionPending,
  onClose,
  onPrimaryAction,
  onEdit,
  onArchive,
  ValueDisplay,
}: {
  noun: string;
  title: string;
  subtitle?: string;
  images: RecordImage[];
  entries: DetailEntry[];
  primaryActions: WorkspaceMutation[];
  secondaryActions: WorkspaceMutation[];
  canUpdate: boolean;
  canArchive: boolean;
  updateLabel?: string;
  archiveLabel?: string;
  actionPending: boolean;
  onClose: () => void;
  onPrimaryAction: (mutation: WorkspaceMutation) => void;
  onEdit: () => void;
  onArchive: () => void;
  ValueDisplay: ValueDisplayComponent;
}) {
  const chips = entries.filter(
    (entry) =>
      CHIP_KEYS.has(entry.key) ||
      entry.format === "status" ||
      entry.key.endsWith("_status") ||
      entry.key.endsWith("_type"),
  );
  const chipKeys = new Set(chips.map((entry) => entry.key));
  const remaining = entries.filter((entry) => !chipKeys.has(entry.key));
  const prose = remaining.filter(
    (entry) =>
      entry.richtext ||
      PROSE_KEYS.has(entry.key) ||
      entry.format === "richtext",
  );
  const proseKeys = new Set(prose.map((entry) => entry.key));
  const spotlight = remaining.filter(
    (entry) =>
      !proseKeys.has(entry.key) &&
      (SPOTLIGHT_KEYS.has(entry.key) || entry.key === "when"),
  );
  const spotlightKeys = new Set(spotlight.map((entry) => entry.key));
  const meta = remaining.filter(
    (entry) => !proseKeys.has(entry.key) && !spotlightKeys.has(entry.key),
  );
  const hero = images[0];
  const extraImages = images.slice(1, 5);

  return (
    <div className="flex flex-col">
      <header className="border-b border-line/80 pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="eyebrow text-coral">{noun}</p>
            <h2 className="display-type mt-2 text-[1.85rem] leading-[1.1] break-words sm:text-3xl">
              {title}
            </h2>
            {subtitle ? (
              <p className="mt-2 text-sm leading-6 text-muted">{subtitle}</p>
            ) : null}
            {chips.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {chips.map((entry) => (
                  <span
                    key={entry.key}
                    className={cn(
                      "inline-flex rounded-full px-2.5 py-1 text-[.68rem] font-bold tracking-wide",
                      statusTone(entry.value),
                    )}
                  >
                    {formatPlain(entry.value, entry.key)}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="shrink-0"
            onClick={onClose}
            aria-label="Close details"
          >
            <X className="size-5" />
          </Button>
        </div>

        {(primaryActions.length > 0 ||
          secondaryActions.length > 0 ||
          canUpdate ||
          canArchive) && (
          <div className="mt-4 flex flex-col gap-2">
            {primaryActions.length ? (
              <div className="flex flex-wrap gap-2">
                {primaryActions.map((item) => (
                  <Button
                    key={item.label}
                    size="sm"
                    variant={item.danger ? "danger" : "primary"}
                    className="min-w-[8.5rem]"
                    disabled={actionPending}
                    onClick={() => onPrimaryAction(item)}
                  >
                    {actionPending ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : null}
                    {item.label}
                  </Button>
                ))}
              </div>
            ) : null}
            {(secondaryActions.length > 0 || canUpdate || canArchive) && (
              <div className="flex flex-wrap gap-2">
                {secondaryActions.map((item) => (
                  <Button
                    key={item.label}
                    size="sm"
                    variant="outline"
                    className={
                      item.danger
                        ? "border-red-500/30 text-red-700 hover:bg-red-500/10"
                        : undefined
                    }
                    disabled={actionPending}
                    onClick={() => onPrimaryAction(item)}
                  >
                    {actionPending ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : null}
                    {item.label}
                  </Button>
                ))}
                {canUpdate ? (
                  <Button size="sm" variant="outline" onClick={onEdit}>
                    <Pencil className="size-4" /> {updateLabel ?? "Edit"}
                  </Button>
                ) : null}
                {canArchive ? (
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-red-500/30 text-red-700 hover:bg-red-500/10"
                    disabled={actionPending}
                    onClick={onArchive}
                  >
                    <Archive className="size-4" /> {archiveLabel ?? "Archive"}
                  </Button>
                ) : null}
              </div>
            )}
          </div>
        )}
      </header>

      <div className="mt-5 grid flex-1 gap-6 pb-2">
        {hero ? (
          <section aria-label="Featured media" className="grid gap-2">
            <div className="relative aspect-[16/10] overflow-hidden rounded-2xl border border-line bg-panel">
              <Image
                fill
                unoptimized
                alt={hero.alt}
                className="object-cover"
                sizes="(max-width: 640px) 100vw, 36rem"
                src={`/api/v1/media/${hero.id}/content`}
              />
            </div>
            {extraImages.length ? (
              <div className="grid grid-cols-4 gap-2">
                {extraImages.map((image) => (
                  <div
                    key={image.id}
                    className="relative aspect-square overflow-hidden rounded-xl border border-line bg-panel"
                  >
                    <Image
                      fill
                      unoptimized
                      alt={image.alt}
                      className="object-cover"
                      sizes="96px"
                      src={`/api/v1/media/${image.id}/content`}
                    />
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

        {spotlight.length ? (
          <section
            aria-label="Key details"
            className="overflow-hidden rounded-2xl border border-line bg-panel/70"
          >
            <dl className="divide-y divide-line">
              {spotlight.map((entry) => (
                <div
                  key={entry.key}
                  className="grid gap-1 px-4 py-3.5 sm:grid-cols-[6.5rem_1fr] sm:items-start sm:gap-4"
                >
                  <dt className="text-[.68rem] font-bold tracking-[.08em] text-muted uppercase">
                    {entry.label}
                  </dt>
                  <dd className="min-w-0 text-sm leading-6 font-semibold text-ink">
                    <ValueNode entry={entry} ValueDisplay={ValueDisplay} />
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}

        {prose.length
          ? prose.map((entry) => (
              <section key={entry.key} className="grid gap-2">
                <h3 className="text-[.68rem] font-bold tracking-[.1em] text-muted uppercase">
                  {entry.label}
                </h3>
                <div className="rounded-2xl border border-line bg-panel/45 px-4 py-4 text-sm leading-7 text-ink">
                  <ValueNode entry={entry} ValueDisplay={ValueDisplay} prose />
                </div>
              </section>
            ))
          : null}

        {meta.length ? (
          <section aria-label="More details" className="grid gap-3">
            <h3 className="text-[.68rem] font-bold tracking-[.1em] text-muted uppercase">
              More details
            </h3>
            <dl className="grid gap-3">
              {meta.map((entry) => (
                <div
                  key={entry.key}
                  className="grid gap-1 border-b border-line/80 pb-3 last:border-b-0 last:pb-0 sm:grid-cols-[7rem_1fr] sm:gap-4"
                >
                  <dt className="text-[.65rem] font-bold tracking-[.08em] text-muted uppercase">
                    {entry.label}
                  </dt>
                  <dd className="min-w-0 text-sm leading-6 text-ink">
                    <ValueNode entry={entry} ValueDisplay={ValueDisplay} />
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}

        {!spotlight.length && !prose.length && !meta.length ? (
          <p className="rounded-2xl border border-dashed border-line bg-panel/40 px-4 py-8 text-center text-sm text-muted">
            No additional details for this {noun.toLowerCase()}.
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function detailEntryLabel(key: string, label?: string) {
  return label ?? humanize(key);
}
