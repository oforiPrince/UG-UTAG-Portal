"use client";

import { Trash2, Check, LoaderCircle, Minus, Pencil, X } from "lucide-react";
import Image from "next/image";
import type { ComponentType } from "react";

import { WorkspaceRichTextValue } from "@/components/dashboard/workspace-rich-text-value";
import { Button } from "@/components/ui/button";
import { display, displayChoice } from "@/lib/workspace-display";
import type { WorkspaceDetailField } from "@/lib/workspace-detail";
import type { WorkspaceMutation } from "@/lib/workspaces";
import type { WorkspaceDetailSection } from "@/lib/workspace-presentation";
import { cn, humanize } from "@/lib/utils";

export { partitionDetailActions } from "@/lib/workspace-row-actions";

export type DetailEntry = {
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

function isBooleanEntry(entry: DetailEntry) {
  if (typeof entry.value === "boolean") return true;
  return (
    entry.format === "boolean" &&
    (entry.value === "true" || entry.value === "false")
  );
}

function BooleanBadge({ value }: { value: unknown }) {
  const yes = value === true || value === "true";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[.68rem] font-bold tracking-wide",
        yes
          ? "bg-emerald-500/12 text-emerald-800 dark:text-emerald-300"
          : "bg-ink/6 text-ink/60",
      )}
    >
      {yes ? (
        <Check className="size-3.5" aria-hidden="true" />
      ) : (
        <Minus className="size-3.5" aria-hidden="true" />
      )}
      {yes ? "Yes" : "No"}
    </span>
  );
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
  if (isBooleanEntry(entry)) {
    return <BooleanBadge value={entry.value} />;
  }
  if (entry.richtext && typeof entry.value === "string") {
    return (
      <div
        className={
          prose
            ? "[&_.rich-text-content]:text-sm [&_.rich-text-content]:leading-7"
            : undefined
        }
      >
        <WorkspaceRichTextValue html={entry.value} />
      </div>
    );
  }
  if (
    prose &&
    (typeof entry.value === "string" || typeof entry.value === "number")
  ) {
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
  heroShape = "landscape",
  entries,
  primaryActions,
  secondaryActions,
  canUpdate,
  canDelete,
  updateLabel,
  deleteLabel,
  actionPending,
  onClose,
  onPrimaryAction,
  onEdit,
  onDelete,
  ValueDisplay,
  sections = [],
  variant = "dialog",
}: {
  noun: string;
  title: string;
  subtitle?: string;
  images: RecordImage[];
  heroShape?: "landscape" | "portrait";
  entries: DetailEntry[];
  primaryActions: WorkspaceMutation[];
  secondaryActions: WorkspaceMutation[];
  canUpdate: boolean;
  canDelete: boolean;
  updateLabel?: string;
  deleteLabel?: string;
  actionPending: boolean;
  onClose?: () => void;
  onPrimaryAction: (mutation: WorkspaceMutation) => void;
  onEdit: () => void;
  onDelete: () => void;
  ValueDisplay: ValueDisplayComponent;
  sections?: WorkspaceDetailSection[];
  variant?: "dialog" | "page";
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
  const flags = meta.filter(isBooleanEntry);
  const facts = meta.filter((entry) => !isBooleanEntry(entry));
  const hero = images[0];
  const portraitHero = heroShape === "portrait" ? hero : undefined;
  const galleryHero = portraitHero ? undefined : hero;
  const extraImages = images.slice(1, 5);
  const entriesByKey = new Map(entries.map((entry) => [entry.key, entry]));
  const sectionGroups = sections
    .map((section) => ({
      ...section,
      entries: section.fieldKeys.flatMap((key) => {
        const entry = entriesByKey.get(key);
        return entry && !chipKeys.has(key) ? [entry] : [];
      }),
    }))
    .filter((section) => section.entries.length > 0);
  const hasActions =
    primaryActions.length > 0 ||
    secondaryActions.length > 0 ||
    canUpdate ||
    canDelete;

  return (
    <div
      className={cn(
        "flex flex-col",
        variant === "page" && "mx-auto w-full max-w-5xl",
      )}
    >
      <header
        className={cn(
          "relative overflow-hidden",
          variant === "page"
            ? portraitHero
              ? "rounded-2xl bg-[#0b1a2e] text-paper"
              : "workspace-folio rounded-2xl p-5 sm:p-6"
            : "border-b border-line/70 pb-4",
        )}
      >
        <div
          className={cn(
            "grid items-start gap-5",
            variant === "page" &&
              hasActions &&
              "lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-10",
            variant === "page" && portraitHero && "p-5 sm:p-6",
          )}
        >
          <div
            className={cn("flex min-w-0 items-start gap-5", onClose && "pr-12")}
          >
            {portraitHero ? (
              <div className="relative w-16 shrink-0 overflow-hidden rounded-xl bg-white/8 sm:w-20">
                <div className="relative aspect-[4/5]">
                  <Image
                    fill
                    unoptimized
                    alt={portraitHero.alt}
                    className="object-cover"
                    sizes="80px"
                    src={`/api/v1/media/${portraitHero.id}/content`}
                  />
                </div>
              </div>
            ) : null}
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  "eyebrow",
                  variant === "page" && portraitHero ? "text-gold" : "text-coral",
                )}
              >
                {noun}
              </p>
              <h2
                className={cn(
                  "mt-1.5 max-w-3xl text-xl leading-snug font-semibold tracking-tight break-words sm:text-2xl",
                  variant === "page" && portraitHero && "text-paper",
                )}
              >
                {title}
              </h2>
              {subtitle ? (
                <p
                  className={cn(
                    "mt-2 max-w-2xl text-sm leading-6",
                    variant === "page" && portraitHero
                      ? "text-white/62"
                      : "text-muted",
                  )}
                >
                  {subtitle}
                </p>
              ) : null}
              {chips.length ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {chips.map((entry) => (
                    <span
                      key={entry.key}
                      className={cn(
                        "inline-flex rounded-full px-2.5 py-1 text-[.68rem] font-bold tracking-wide",
                        variant === "page" && portraitHero
                          ? "bg-white/10 text-paper"
                          : statusTone(entry.value),
                      )}
                    >
                      {formatPlain(entry.value, entry.key)}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
          {onClose ? (
            <Button
              size="icon"
              variant="ghost"
              className={cn(
                "absolute top-0 right-0 shrink-0",
                variant === "page" && portraitHero && "text-white/70 hover:bg-white/10 hover:text-white",
              )}
              onClick={onClose}
              aria-label="Close details"
            >
              <X className="size-5" />
            </Button>
          ) : null}
          {hasActions ? (
            <div
              className={cn(
                "flex flex-col gap-2",
                variant === "page" && "lg:max-w-[22rem] lg:items-end",
              )}
            >
              {primaryActions.length ? (
                <div
                  className={cn(
                    "flex flex-wrap gap-2",
                    variant === "page" && "lg:justify-end",
                  )}
                >
                  {primaryActions.map((item) => (
                    <Button
                      key={item.label}
                      size="sm"
                      variant={item.danger ? "danger" : "primary"}
                      className={cn(
                        "min-w-[7.5rem]",
                        variant === "page" &&
                          portraitHero &&
                          !item.danger &&
                          "bg-paper text-ink hover:bg-paper/90",
                      )}
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
              {(secondaryActions.length > 0 || canUpdate || canDelete) && (
                <div
                  className={cn(
                    "flex flex-wrap gap-2",
                    variant === "page" && "lg:justify-end",
                  )}
                >
                  {secondaryActions.map((item) => (
                    <Button
                      key={item.label}
                      size="sm"
                      variant="ghost"
                      className={
                        item.danger
                          ? "text-red-700 hover:bg-red-500/10 dark:text-red-300"
                          : variant === "page" && portraitHero
                            ? "text-white/75 hover:bg-white/10 hover:text-white"
                            : "text-muted hover:text-ink"
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
                    <Button
                      size="sm"
                      variant="ghost"
                      className={
                        variant === "page" && portraitHero
                          ? "text-white/75 hover:bg-white/10 hover:text-white"
                          : "text-muted hover:text-ink"
                      }
                      onClick={onEdit}
                    >
                      <Pencil className="size-4" /> {updateLabel ?? "Edit"}
                    </Button>
                  ) : null}
                  {canDelete ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      className={
                        variant === "page" && portraitHero
                          ? "text-red-200 hover:bg-white/10"
                          : "text-red-700 hover:bg-red-500/10 dark:text-red-300"
                      }
                      disabled={actionPending}
                      onClick={onDelete}
                    >
                      <Trash2 className="size-4" /> {deleteLabel ?? "Delete"}
                    </Button>
                  ) : null}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </header>

      <div
        className={cn(
          "mt-5 grid flex-1 gap-5 pb-2",
          variant === "page" && "lg:grid-cols-2 lg:gap-x-8 lg:gap-y-8",
        )}
      >
        {galleryHero || extraImages.length ? (
          <section
            aria-label="Featured media"
            className={cn("grid gap-3", variant === "page" && "lg:col-span-2")}
          >
            {galleryHero ? (
              <div
                className={cn(
                  "relative overflow-hidden rounded-xl bg-ink/5",
                  variant === "page"
                    ? "h-[clamp(11rem,28vw,18rem)]"
                    : "aspect-[16/10]",
                )}
              >
                <Image
                  fill
                  unoptimized
                  alt={galleryHero.alt}
                  className="object-cover"
                  sizes="(max-width: 640px) 100vw, 36rem"
                  src={`/api/v1/media/${galleryHero.id}/content`}
                />
              </div>
            ) : null}
            {extraImages.length ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {extraImages.map((image) => (
                  <div
                    key={image.id}
                    className={cn(
                      "relative overflow-hidden rounded-2xl bg-ink/5",
                      variant === "page" ? "h-28 sm:h-36" : "aspect-square",
                    )}
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

        {sectionGroups.length
          ? sectionGroups.map((section, sectionIndex) => {
              const sectionProse = section.entries.filter(
                (entry) =>
                  entry.richtext ||
                  PROSE_KEYS.has(entry.key) ||
                  entry.format === "richtext",
              );
              const proseKeys = new Set(sectionProse.map((entry) => entry.key));
              const sectionFacts = section.entries.filter(
                (entry) => !proseKeys.has(entry.key),
              );
              return (
                <section
                  key={section.id}
                  aria-labelledby={`detail-section-${section.id}`}
                  className={cn(
                    "grid gap-5",
                    variant !== "page" &&
                      sectionIndex > 0 &&
                      "border-t border-line pt-6",
                    variant === "page" &&
                      sectionProse.length > 0 &&
                      "lg:col-span-2",
                  )}
                >
                  {variant === "page" ? (
                    <div>
                      <div className="flex items-end gap-4">
                        <span className="eyebrow text-gold">
                          {String(sectionIndex + 1).padStart(2, "0")}
                        </span>
                        <span className="workspace-rule mb-1.5 flex-1" />
                      </div>
                      <h3
                        id={`detail-section-${section.id}`}
                        className="mt-2 text-lg font-semibold tracking-tight"
                      >
                        {section.title}
                      </h3>
                      {section.description ? (
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                          {section.description}
                        </p>
                      ) : null}
                    </div>
                  ) : (
                    <div>
                      <p className="eyebrow text-coral">{noun}</p>
                      <h3
                        id={`detail-section-${section.id}`}
                        className="mt-1.5 text-base font-semibold tracking-tight"
                      >
                        {section.title}
                      </h3>
                      {section.description ? (
                        <p className="mt-2 text-sm leading-6 text-muted">
                          {section.description}
                        </p>
                      ) : null}
                    </div>
                  )}
                  {sectionProse.map((entry) => (
                    <div key={entry.key} className="grid gap-2">
                      <h4 className="text-[.68rem] font-bold tracking-[.1em] text-muted uppercase">
                        {entry.label}
                      </h4>
                      <div
                        className={cn(
                          "text-sm leading-7 text-ink",
                          variant === "page"
                            ? "border-l-2 border-gold/70 pl-4"
                            : "rounded-2xl bg-panel/70 px-4 py-4",
                        )}
                      >
                        <ValueNode
                          entry={entry}
                          ValueDisplay={ValueDisplay}
                          prose
                        />
                      </div>
                    </div>
                  ))}
                  {sectionFacts.length ? (
                    <dl
                      className={cn(
                        "grid sm:grid-cols-2",
                        variant === "page" ? "gap-x-8 gap-y-5" : "gap-3",
                      )}
                    >
                      {sectionFacts.map((entry) => (
                        <div key={entry.key} className="min-w-0">
                          <dt className="text-[.62rem] font-bold tracking-[.1em] text-muted uppercase">
                            {entry.label}
                          </dt>
                          <dd className="mt-1.5 min-w-0 text-sm leading-6 font-medium text-ink">
                            <ValueNode
                              entry={entry}
                              ValueDisplay={ValueDisplay}
                            />
                          </dd>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                </section>
              );
            })
          : null}

        {!sectionGroups.length && spotlight.length ? (
          <section
            aria-label="Key details"
            className={cn(variant === "page" && "lg:col-span-2")}
          >
            <div className="flex items-end gap-4">
              <span className="eyebrow text-gold">01</span>
              <span className="workspace-rule mb-1.5 flex-1" />
            </div>
            <h3 className="mt-2 text-lg font-semibold tracking-tight">Key details</h3>
            <dl className="mt-5 grid gap-x-8 gap-y-5 sm:grid-cols-2">
              {spotlight.map((entry) => (
                <div key={entry.key} className="min-w-0">
                  <dt className="text-[.62rem] font-bold tracking-[.1em] text-muted uppercase">
                    {entry.label}
                  </dt>
                  <dd className="mt-1.5 min-w-0 text-sm leading-6 font-medium text-ink">
                    <ValueNode entry={entry} ValueDisplay={ValueDisplay} />
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}

        {!sectionGroups.length && prose.length
          ? prose.map((entry) => (
              <section
                key={entry.key}
                className={cn(
                  "grid gap-2",
                  variant === "page" && "lg:col-span-2",
                )}
              >
                <h3 className="text-[.68rem] font-bold tracking-[.1em] text-muted uppercase">
                  {entry.label}
                </h3>
                <div className="border-l-2 border-gold/70 pl-4 text-sm leading-7 text-ink">
                  <ValueNode entry={entry} ValueDisplay={ValueDisplay} prose />
                </div>
              </section>
            ))
          : null}

        {!sectionGroups.length && meta.length ? (
          <section
            aria-label="Additional information"
            className={cn("grid gap-5", variant === "page" && "lg:col-span-2")}
          >
            <div>
              <div className="flex items-end gap-4">
                <span className="eyebrow text-gold">
                  {spotlight.length || prose.length ? "02" : "01"}
                </span>
                <span className="workspace-rule mb-1.5 flex-1" />
              </div>
              <h3 className="mt-2 text-lg font-semibold tracking-tight">
                Additional information
              </h3>
            </div>
            {facts.length ? (
              <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
                {facts.map((entry) => (
                  <div key={entry.key} className="min-w-0">
                    <dt className="text-[.62rem] font-bold tracking-[.1em] text-muted uppercase">
                      {entry.label}
                    </dt>
                    <dd className="mt-1.5 min-w-0 text-sm leading-6 text-ink">
                      <ValueNode entry={entry} ValueDisplay={ValueDisplay} />
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {flags.length ? (
              <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
                {flags.map((entry) => (
                  <div
                    key={entry.key}
                    className="flex items-center justify-between gap-3"
                  >
                    <dt className="text-[.62rem] font-bold tracking-[.1em] text-muted uppercase">
                      {entry.label}
                    </dt>
                    <dd className="shrink-0">
                      <BooleanBadge value={entry.value} />
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </section>
        ) : null}

        {!sectionGroups.length &&
        !spotlight.length &&
        !prose.length &&
        !meta.length ? (
          <p
            className={cn(
              "rounded-2xl bg-panel/50 px-4 py-10 text-center text-sm text-muted",
              variant === "page" && "lg:col-span-2",
            )}
          >
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
