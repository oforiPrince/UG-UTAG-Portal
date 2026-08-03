"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowDownToLine,
  ArrowLeft,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  Filter,
  LoaderCircle,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { WorkspacePanelPreview } from "@/components/dashboard/workspace-panel-preview";
import {
  RecordDetailsView,
} from "@/components/dashboard/record-details-view";
import { WorkspaceRowActions } from "@/components/dashboard/workspace-row-actions";
import { RichTextEditor } from "@/components/dashboard/rich-text-editor";
import { WorkspaceMediaField } from "@/components/dashboard/workspace-media-field";
import { WorkspaceRichTextValue } from "@/components/dashboard/workspace-rich-text-value";
import { API_URL, api } from "@/lib/api";
import {
  defaultDeliveryCapabilities,
  deliveryAvailable as isDeliveryAvailable,
} from "@/lib/delivery-capabilities";
import { display, displayChoice } from "@/lib/workspace-display";
import { visibleDetailEntries } from "@/lib/workspace-detail";
import { rowActionsFor } from "@/lib/workspace-row-actions";
import {
  documentAudiencesForCategory,
  nextMultiSelectValue,
  workspaceOptionQueryState,
} from "@/lib/workspace-options";
import {
  workspaceDetailFields,
  workspaceFilterMatches,
  workspaceRowFromMutationResult,
} from "@/lib/workspaces";
import type {
  WorkspaceConfig,
  WorkspaceField,
  WorkspaceMutation,
  WorkspacePreviewKind,
  WorkspaceRow,
} from "@/lib/workspaces";
import { humanize } from "@/lib/utils";

type FormValue = string | boolean | string[];
type FormValues = Record<string, FormValue>;
type User = { id: string; permissions: string[] };

const PAGE_SIZE = 15;
type PageResponse = {
  items: WorkspaceRow[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

function useDebouncedValue(value: string, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timeout);
  }, [delay, value]);
  return debounced;
}

function optionEndpoint(
  source: NonNullable<WorkspaceField["optionSource"]>,
  search: string,
) {
  if (!source.searchParam || !search.trim()) return source.endpoint;
  const separator = source.endpoint.includes("?") ? "&" : "?";
  return `${source.endpoint}${separator}${encodeURIComponent(source.searchParam)}=${encodeURIComponent(search.trim())}`;
}

function workspaceEndpoint(
  config: WorkspaceConfig,
  page: number,
  search: string,
  filters: Record<string, string>,
) {
  if (!config.serverPagination) return config.endpoint;
  const [path, existing = ""] = config.endpoint.split("?", 2);
  const params = new URLSearchParams(existing);
  params.set("page", String(page));
  params.set("page_size", String(PAGE_SIZE));
  if (config.serverPagination.searchParam) {
    const value = search.trim();
    if (value) params.set(config.serverPagination.searchParam, value);
    else params.delete(config.serverPagination.searchParam);
  }
  for (const [field, parameter] of Object.entries(
    config.serverPagination.filterParams ?? {},
  )) {
    const value = filters[field];
    if (value) params.set(parameter, value);
    else params.delete(parameter);
  }
  return `${path}?${params}`;
}

function pageResponse(data: unknown): PageResponse | null {
  if (
    !data ||
    typeof data !== "object" ||
    !("items" in data) ||
    !Array.isArray((data as { items: unknown }).items)
  ) {
    return null;
  }
  const result = data as Partial<PageResponse>;
  if (
    typeof result.page !== "number" ||
    typeof result.total !== "number" ||
    typeof result.pages !== "number"
  ) {
    return null;
  }
  return result as PageResponse;
}

export function rowsFrom(data: unknown): WorkspaceRow[] {
  if (Array.isArray(data)) return data as WorkspaceRow[];
  if (
    data &&
    typeof data === "object" &&
    "items" in data &&
    Array.isArray((data as { items: unknown }).items)
  ) {
    return (data as { items: WorkspaceRow[] }).items;
  }
  if (data && typeof data === "object") {
    return Object.entries(data).flatMap(([group, value]) =>
      value && typeof value === "object"
        ? Object.entries(value as Record<string, unknown>).map(
            ([key, item]) => ({
              group,
              key,
              value: item,
            }),
          )
        : [{ key: group, value }],
    );
  }
  return [];
}

export function WorkspaceSelect({
  id,
  labelledBy,
  field,
  value,
  autoFocus,
  onChange,
}: {
  id: string;
  labelledBy: string;
  field: WorkspaceField;
  value: FormValue;
  autoFocus: boolean;
  onChange: (value: string) => void;
}) {
  const source = field.optionSource;
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const remoteSearch = useDebouncedValue(source?.searchParam ? search : "");
  const optionsQuery = useQuery({
    queryKey: [
      "workspace-options",
      source?.queryKey ?? field.key,
      remoteSearch,
    ],
    queryFn: () => api<unknown>(optionEndpoint(source!, remoteSearch)),
    enabled: Boolean(source),
    staleTime: 30_000,
  });
  const dynamicOptions = source
    ? rowsFrom(optionsQuery.data)
        .filter((row) => source.filter?.(row) ?? true)
        .map((row) => ({ value: source.value(row), label: source.label(row) }))
    : [];
  const options = source
    ? dynamicOptions
    : (field.options ?? []).map((option) => ({
        value: option,
        label: humanize(option),
      }));
  const optionState = workspaceOptionQueryState(Boolean(source), optionsQuery);
  const emptyLabel = optionState.isLoading
    ? "Loading available options…"
    : optionState.isError
      ? "Options unavailable — refresh and try again"
      : source && options.length === 0
        ? (source.emptyLabel ?? "No options available")
        : "Select";

  const searchable = Boolean(source) || options.length > 10;
  const containerRef = useRef<HTMLDivElement>(null);
  const selectedOption = options.find(
    (option) => option.value === String(value),
  );
  const filteredOptions =
    source?.searchParam && remoteSearch.trim() === search.trim()
      ? options
      : options.filter((option) =>
          option.label.toLowerCase().includes(search.trim().toLowerCase()),
        );

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () =>
      document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [open]);

  if (searchable) {
    const disabled = Boolean(source) && optionState.isLoading;
    return (
      <div
        ref={containerRef}
        className="relative"
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.stopPropagation();
            setOpen(false);
          }
        }}
      >
        <button
          id={id}
          type="button"
          role="combobox"
          aria-labelledby={labelledBy}
          aria-expanded={open}
          aria-controls={`${id}-options`}
          aria-haspopup="listbox"
          autoFocus={autoFocus}
          disabled={disabled}
          onClick={() => setOpen((current) => !current)}
          className="flex min-h-12 w-full items-center justify-between gap-3 rounded-xl border border-line bg-panel px-4 text-left text-sm font-normal outline-none focus:border-ink/25 disabled:cursor-not-allowed disabled:opacity-70"
        >
          <span className={selectedOption ? "text-ink" : "text-muted"}>
            {selectedOption?.label ?? emptyLabel}
          </span>
          {optionState.isLoading ? (
            <LoaderCircle className="size-4 shrink-0 animate-spin text-muted" />
          ) : (
            <ChevronDown
              className={`size-4 shrink-0 text-muted transition ${open ? "rotate-180" : ""}`}
            />
          )}
        </button>
        {open ? (
          <div className="absolute z-50 mt-2 w-full min-w-64 overflow-hidden rounded-xl border border-line bg-paper shadow-xl">
            <label className="flex min-h-11 items-center gap-2 border-b border-line px-3">
              <Search className="size-4 shrink-0 text-muted" />
              <span className="sr-only">Search {field.label}</span>
              <input
                autoFocus
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={`Search ${field.label.toLowerCase()}`}
                className="w-full bg-transparent text-sm font-normal outline-none"
              />
            </label>
            <div
              id={`${id}-options`}
              role="listbox"
              aria-labelledby={labelledBy}
              className="scrollbar-subtle max-h-64 overflow-y-auto p-1.5"
            >
              {optionState.isLoading ? (
                <p className="px-3 py-4 text-center text-xs font-normal text-muted">
                  Searching available options…
                </p>
              ) : optionState.isError ? (
                <div className="grid justify-items-center gap-2 px-3 py-4 text-center">
                  <p className="text-xs font-normal text-red-700">
                    Options could not be loaded.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => optionsQuery.refetch()}
                  >
                    <RefreshCw className="size-3.5" /> Try again
                  </Button>
                </div>
              ) : !field.required && value ? (
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => {
                    onChange("");
                    setSearch("");
                    setOpen(false);
                  }}
                  className="flex min-h-10 w-full items-center rounded-lg px-3 text-left text-xs text-muted hover:bg-ink/[.04]"
                >
                  Clear selection
                </button>
              ) : null}
              {!optionState.isLoading && !optionState.isError
                ? filteredOptions.map((option) => {
                    const isSelected = option.value === String(value);
                    return (
                      <button
                        key={option.value}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => {
                          onChange(option.value);
                          setSearch("");
                          setOpen(false);
                        }}
                        className="flex min-h-10 w-full items-center justify-between gap-3 rounded-lg px-3 text-left text-xs hover:bg-ink/[.04]"
                      >
                        <span>{option.label}</span>
                        {isSelected ? (
                          <Check className="size-4 shrink-0 text-sky" />
                        ) : null}
                      </button>
                    );
                  })
                : null}
              {!optionState.isLoading &&
              !optionState.isError &&
              filteredOptions.length === 0 ? (
                <p className="px-3 py-4 text-center text-xs font-normal text-muted">
                  {options.length
                    ? "No matching options"
                    : (source?.emptyLabel ?? "No options available")}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <select
      id={id}
      aria-labelledby={labelledBy}
      autoFocus={autoFocus}
      required={field.required}
      value={String(value)}
      disabled={
        Boolean(source) &&
        (optionState.isLoading || optionState.isError || options.length === 0)
      }
      onChange={(event) => onChange(event.target.value)}
      className="min-h-12 rounded-xl border border-line bg-panel px-4 text-sm font-normal outline-none focus:border-ink/25 disabled:cursor-not-allowed disabled:opacity-70"
    >
      <option value="">{emptyLabel}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

function WorkspaceMultiSelect({
  id,
  labelledBy,
  field,
  value,
  onChange,
}: {
  id: string;
  labelledBy: string;
  field: WorkspaceField;
  value: FormValue;
  onChange: (value: string[]) => void;
}) {
  const source = field.optionSource;
  const [search, setSearch] = useState("");
  const remoteSearch = useDebouncedValue(source?.searchParam ? search : "");
  const optionsQuery = useQuery({
    queryKey: [
      "workspace-options",
      source?.queryKey ?? field.key,
      remoteSearch,
    ],
    queryFn: () => api<unknown>(optionEndpoint(source!, remoteSearch)),
    enabled: Boolean(source),
    staleTime: 30_000,
  });
  const options = source
    ? rowsFrom(optionsQuery.data)
        .filter((row) => source.filter?.(row) ?? true)
        .map((row) => ({ value: source.value(row), label: source.label(row) }))
    : (field.options ?? []).map((option) => ({
        value: option,
        label: humanize(option),
      }));
  const selected = Array.isArray(value) ? value : value ? [String(value)] : [];
  const optionState = workspaceOptionQueryState(Boolean(source), optionsQuery);
  const searchable = Boolean(source) || options.length > 10;
  const filteredOptions =
    source?.searchParam && remoteSearch.trim() === search.trim()
      ? options
      : options.filter((option) =>
          option.label.toLowerCase().includes(search.trim().toLowerCase()),
        );

  return (
    <fieldset
      id={id}
      aria-labelledby={labelledBy}
      className="max-h-64 overflow-y-auto rounded-xl border border-line bg-panel p-2"
    >
      <legend className="sr-only">{field.label}</legend>
      {searchable ? (
        <label className="sticky top-0 z-10 mb-1 flex min-h-10 items-center gap-2 rounded-lg bg-panel px-2">
          <Search className="size-4 shrink-0 text-muted" />
          <span className="sr-only">Search {field.label}</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={`Search ${field.label.toLowerCase()}`}
            className="w-full bg-transparent text-xs font-normal outline-none"
          />
        </label>
      ) : null}
      {optionState.isLoading ? (
        <p className="px-2 py-3 text-xs font-normal text-muted">
          Loading available options…
        </p>
      ) : optionState.isError ? (
        <div className="grid justify-items-start gap-2 px-2 py-3">
          <p className="text-xs font-normal text-red-700">
            Options could not be loaded.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => optionsQuery.refetch()}
          >
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </div>
      ) : filteredOptions.length === 0 ? (
        <p className="px-2 py-3 text-xs font-normal text-muted">
          {options.length
            ? "No matching options"
            : (source?.emptyLabel ?? "No options available")}
        </p>
      ) : (
        filteredOptions.map((option) => (
          <label
            key={option.value}
            className="flex min-h-10 items-center gap-3 rounded-lg px-2 text-xs font-normal hover:bg-ink/[.035]"
          >
            <input
              type="checkbox"
              checked={selected.includes(option.value)}
              onChange={(event) =>
                onChange(
                  nextMultiSelectValue(
                    selected,
                    option.value,
                    event.target.checked,
                  ),
                )
              }
              className="size-4 accent-sky"
            />
            {option.label}
          </label>
        ))
      )}
    </fieldset>
  );
}

function isEmptyValue(value: unknown) {
  return (
    value == null ||
    value === "" ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === "object" &&
      !Array.isArray(value) &&
      Object.keys(value).length === 0)
  );
}

function objectItemLabel(item: WorkspaceRow, index: number) {
  for (const key of [
    "media_name",
    "filename",
    "original_filename",
    "title",
    "name",
    "label",
    "full_name",
  ]) {
    const value = item[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return `Item ${index + 1}`;
}

function objectItemMeta(item: WorkspaceRow) {
  const skip = new Set([
    "media_name",
    "filename",
    "original_filename",
    "title",
    "name",
    "label",
    "full_name",
    "position",
  ]);
  return Object.entries(item)
    .filter(([key, value]) => {
      if (skip.has(key) || isTechnicalField(key) || isEmptyValue(value)) {
        return false;
      }
      return true;
    })
    .map(([key, value]) => {
      if (key.endsWith("_url") && typeof value === "string" && value) {
        return { key, label: humanize(key), href: value, text: "Open" };
      }
      return {
        key,
        label: humanize(key),
        text: display(value, key),
      };
    });
}

function ValueDisplay({
  value,
  fieldKey,
  compact = false,
}: {
  value: unknown;
  fieldKey: string;
  compact?: boolean;
}) {
  if (isEmptyValue(value)) {
    return <span className="text-muted">Not provided</span>;
  }
  if (Array.isArray(value)) {
    if (compact && value.some((item) => typeof item === "object")) {
      return <>{display(value, fieldKey)}</>;
    }
    if (value.every((item) => typeof item !== "object")) {
      return (
        <span className="flex flex-wrap gap-1.5">
          {value.map((item, index) => (
            <span
              key={`${String(item)}-${index}`}
              className="rounded-full bg-ink/5 px-2.5 py-1 text-[.68rem]"
            >
              {displayChoice(item, fieldKey)}
            </span>
          ))}
        </span>
      );
    }
    return (
      <span className="grid gap-1.5">
        {value.map((item, index) => {
          if (!item || typeof item !== "object") {
            return (
              <span
                key={index}
                className="rounded-lg border border-line bg-panel px-3 py-2 text-[.7rem]"
              >
                {display(item, fieldKey)}
              </span>
            );
          }
          const row = item as WorkspaceRow;
          const label = objectItemLabel(row, index);
          const meta = objectItemMeta(row);
          return (
            <span
              key={index}
              className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg border border-line bg-panel px-3 py-2 text-[.7rem] leading-5"
            >
              <b className="min-w-0 truncate font-bold text-ink">{label}</b>
              {meta.map((entry) =>
                "href" in entry && entry.href ? (
                  <a
                    key={entry.key}
                    href={entry.href}
                    target="_blank"
                    rel="noreferrer"
                    className="shrink-0 font-bold text-coral underline-offset-2 hover:underline"
                  >
                    {entry.text}
                  </a>
                ) : (
                  <span key={entry.key} className="shrink-0 text-muted">
                    <span className="font-semibold text-ink/55">
                      {entry.label}
                    </span>
                    {": "}
                    {entry.text}
                  </span>
                ),
              )}
            </span>
          );
        })}
      </span>
    );
  }
  if (typeof value === "object") {
    return (
      <span className="grid gap-1.5">
        {Object.entries(value as WorkspaceRow)
          .filter(([key]) => !isTechnicalField(key))
          .map(([key, itemValue]) => (
            <span
              key={key}
              className="flex flex-wrap gap-x-2 gap-y-0.5 text-[.7rem] leading-5"
            >
              <span className="font-bold text-muted">{humanize(key)}</span>
              <span>
                {key.endsWith("_url") &&
                typeof itemValue === "string" &&
                itemValue ? (
                  <a
                    href={itemValue}
                    target="_blank"
                    rel="noreferrer"
                    className="font-bold text-coral underline-offset-4 hover:underline"
                  >
                    Open
                  </a>
                ) : (
                  display(itemValue, key)
                )}
              </span>
            </span>
          ))}
      </span>
    );
  }
  return <>{display(value, fieldKey)}</>;
}

const TECHNICAL_FIELDS = new Set([
  "content_json",
  "description_json",
  "id",
  "legacy_id",
  "profile_media_id",
  "request_id",
  "sha256",
  "storage_key",
]);

function isTechnicalField(key: string) {
  return (
    TECHNICAL_FIELDS.has(key) || key.endsWith("_id") || key.endsWith("_ids")
  );
}

type RecordImage = {
  id: string;
  name: string;
  alt: string;
};

function recordImages(row: WorkspaceRow): RecordImage[] {
  const images: RecordImage[] = [];
  const add = (id: unknown, name: unknown, alt: unknown = name) => {
    if (!id) return;
    images.push({
      id: String(id),
      name: name ? String(name) : "Image",
      alt: alt ? String(alt) : "Image preview",
    });
  };

  add(
    row.profile_media_id,
    row.full_name,
    `Profile photo for ${String(row.full_name ?? "member")}`,
  );
  add(row.featured_media_id, row.featured_media_name ?? row.title, row.title);
  if (
    row.media_asset_id &&
    (!row.content_type || String(row.content_type).startsWith("image/"))
  ) {
    add(row.media_asset_id, row.media_name ?? row.title, row.title);
  }
  if (
    row.id &&
    typeof row.content_type === "string" &&
    row.content_type.startsWith("image/") &&
    (!row.status || row.status === "ready")
  ) {
    add(row.id, row.original_filename, row.alt_text ?? row.original_filename);
  }
  if (Array.isArray(row.items)) {
    for (const item of row.items as WorkspaceRow[]) {
      if (
        !item.content_type ||
        String(item.content_type).startsWith("image/")
      ) {
        add(
          item.media_asset_id,
          item.filename ?? item.media_name ?? "Gallery image",
          item.alt_text ?? item.filename,
        );
      }
    }
  }

  return images.filter(
    (image, index) =>
      images.findIndex((candidate) => candidate.id === image.id) === index,
  );
}

function RecordThumbnail({ row }: { row: WorkspaceRow }) {
  const image = recordImages(row)[0];
  if (!image) return null;
  return (
    <span className="relative size-10 shrink-0 overflow-hidden rounded-lg border border-line bg-ink/5">
      <Image
        fill
        unoptimized
        alt=""
        className="object-cover"
        sizes="40px"
        src={`/api/v1/media/${image.id}/content`}
      />
    </span>
  );
}

function RecordCardMedia({
  row,
  aspect = "landscape",
}: {
  row: WorkspaceRow;
  aspect?: "square" | "landscape";
}) {
  const image = recordImages(row)[0];
  const aspectClass =
    aspect === "square" ? "aspect-square" : "aspect-[16/10]";
  const contentType =
    typeof row.content_type === "string" ? row.content_type : "";
  const status = typeof row.status === "string" ? row.status : "";
  const filename =
    typeof row.original_filename === "string"
      ? row.original_filename
      : typeof row.title === "string"
        ? row.title
        : "Asset";

  if (!image) {
    const typeLabel = contentType
      ? contentType.split("/").pop()?.toUpperCase() || contentType
      : status
        ? humanize(status)
        : "File";
    return (
      <div
        className={`flex ${aspectClass} flex-col items-center justify-center gap-1 rounded-t-2xl bg-ink/[.04] px-4 text-center`}
      >
        <span className="text-[.62rem] font-black tracking-wide text-muted uppercase">
          {typeLabel}
        </span>
        <span className="line-clamp-2 text-xs font-bold text-ink/70">
          {filename}
        </span>
      </div>
    );
  }
  return (
    <div
      className={`relative ${aspectClass} overflow-hidden rounded-t-2xl bg-ink/5`}
    >
      <Image
        fill
        unoptimized
        alt={image.alt}
        className="object-cover transition duration-300 group-hover:scale-[1.03]"
        sizes="(max-width: 640px) 100vw, (max-width: 1280px) 50vw, 33vw"
        src={`/api/v1/media/${image.id}/content`}
      />
    </div>
  );
}

function statusField(key: string) {
  return [
    "status",
    "priority",
    "outcome",
    "payment_status",
    "is_active",
    "is_public",
    "is_published",
    "is_private",
    "enabled",
  ].includes(key);
}

function RecordImagePreview({ row }: { row: WorkspaceRow }) {
  const images = recordImages(row);
  if (!images.length) return null;
  return (
    <section aria-label="Image preview" className="mt-5">
      <div className="grid grid-cols-3 gap-2">
        {images.slice(0, 6).map((image) => (
          <div
            key={image.id}
            className="relative aspect-square overflow-hidden rounded-xl border border-line bg-ink/5"
          >
            <Image
              fill
              unoptimized
              alt={image.alt}
              className="object-cover"
              sizes="160px"
              src={`/api/v1/media/${image.id}/content`}
            />
            <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/70 to-transparent px-2 pt-5 pb-1.5 text-[.58rem] font-bold text-white">
              {image.name}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function statusClass(value: unknown) {
  const status = String(value).toLowerCase();
  if (
    [
      "active",
      "published",
      "ready",
      "success",
      "completed",
      "paid",
      "true",
    ].includes(status)
  ) {
    return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
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
    return "bg-red-500/10 text-red-700 dark:text-red-300";
  }
  if (
    ["draft", "queued", "scanning", "pending", "invited", "review"].includes(
      status,
    )
  ) {
    return "bg-gold/15 text-ink";
  }
  return "bg-ink/5 text-muted";
}

function endpointFor(mutation: WorkspaceMutation, row?: WorkspaceRow) {
  if (typeof mutation.endpoint === "string") return mutation.endpoint;
  if (!row) throw new Error("This action requires a selected record");
  return mutation.endpoint(row);
}

function fieldsFor(
  mutation: WorkspaceMutation,
  mode: "create" | "edit",
  permissions: string[],
  deliveryAvailable = true,
) {
  return (mutation.fields ?? [])
    .filter(
      (field) =>
        !(mode === "create" && field.editOnly) &&
        !(mode === "edit" && field.createOnly) &&
        (!field.permission || permissions.includes(field.permission)) &&
        (!field.requiresDelivery || deliveryAvailable),
    )
    .map((field) => {
      if (
        !deliveryAvailable &&
        mode === "create" &&
        field.key === "staff_id"
      ) {
        return {
          ...field,
          required: true,
          help:
            field.help ??
            "Required. The staff ID is the temporary first password until email delivery is configured.",
        };
      }
      return field;
    });
}

function parseStructured(value: FormValue, expectsArray: boolean): unknown {
  if (typeof value !== "string" || !value.trim()) {
    return expectsArray ? [] : {};
  }
  try {
    const parsed = JSON.parse(value) as unknown;
    if (expectsArray) return Array.isArray(parsed) ? parsed : [];
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return expectsArray ? [] : {};
  }
}

function structuredInputValue(value: unknown) {
  if (value == null) return "";
  return typeof value === "object" ? display(value) : String(value);
}

function WorkspaceStructuredEditor({
  id,
  labelledBy,
  field,
  value,
  onChange,
}: {
  id: string;
  labelledBy: string;
  field: WorkspaceField;
  value: FormValue;
  onChange: (value: string) => void;
}) {
  const expectsArray =
    Boolean(field.structuredItemFields) || field.defaultValue === "[]";
  const parsed = parseStructured(value, expectsArray);

  if (expectsArray) {
    const items = Array.isArray(parsed) ? parsed : [];
    const itemFields = field.structuredItemFields ?? [
      { key: "value", label: "Value" },
    ];
    const updateItems = (next: unknown[]) => onChange(JSON.stringify(next));
    return (
      <fieldset
        id={id}
        aria-labelledby={labelledBy}
        className="grid gap-3 rounded-xl border border-line bg-panel p-3"
      >
        <legend className="sr-only">{field.label}</legend>
        {items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line px-4 py-5 text-center text-xs font-normal text-muted">
            No {field.label.toLowerCase()} added.
          </p>
        ) : null}
        {items.map((item, itemIndex) => {
          const itemRecord: WorkspaceRow =
            item && typeof item === "object" && !Array.isArray(item)
              ? (item as WorkspaceRow)
              : { value: item };
          return (
            <div
              key={itemIndex}
              className="grid gap-3 rounded-xl border border-line bg-paper p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-[.65rem] font-black tracking-wide text-muted uppercase">
                  Item {itemIndex + 1}
                </span>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove ${field.label.toLowerCase()} item ${itemIndex + 1}`}
                  onClick={() =>
                    updateItems(
                      items.filter(
                        (_, currentIndex) => currentIndex !== itemIndex,
                      ),
                    )
                  }
                >
                  <Trash2 className="size-4 text-red-700" />
                </Button>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {itemFields.map((itemField) => {
                  const updateItem = (
                    event: React.ChangeEvent<
                      HTMLInputElement | HTMLTextAreaElement
                    >,
                  ) => {
                    const next = [...items];
                    next[itemIndex] = {
                      ...itemRecord,
                      [itemField.key]: event.target.value,
                    };
                    updateItems(next);
                  };
                  return (
                    <label
                      key={itemField.key}
                      className={`grid gap-1.5 text-[.68rem] font-bold ${
                        itemField.type === "textarea" ? "sm:col-span-2" : ""
                      }`}
                    >
                      {itemField.label}
                      {itemField.type === "textarea" ? (
                        <textarea
                          value={structuredInputValue(
                            itemRecord[itemField.key],
                          )}
                          placeholder={itemField.placeholder}
                          onChange={updateItem}
                          className="min-h-24 resize-y rounded-lg border border-line bg-panel p-3 text-xs leading-5 font-normal outline-none focus:border-ink/25"
                        />
                      ) : (
                        <input
                          type={itemField.type ?? "text"}
                          value={structuredInputValue(
                            itemRecord[itemField.key],
                          )}
                          placeholder={itemField.placeholder}
                          onChange={updateItem}
                          className="min-h-11 rounded-lg border border-line bg-panel px-3 text-xs font-normal outline-none focus:border-ink/25"
                        />
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="justify-self-start"
          onClick={() =>
            updateItems([
              ...items,
              Object.fromEntries(
                itemFields.map((itemField) => [itemField.key, ""]),
              ),
            ])
          }
        >
          <CirclePlus className="size-4" />
          {field.addItemLabel ?? `Add ${field.label.toLowerCase()} item`}
        </Button>
      </fieldset>
    );
  }

  const record =
    parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as WorkspaceRow)
      : {};
  const configuredFields = field.structuredFields;
  const entries: {
    key: string;
    label: string;
    placeholder?: string;
    type?: "text" | "email" | "url" | "date" | "time" | "textarea";
    value: unknown;
  }[] = configuredFields
    ? configuredFields.map((item) => ({
        ...item,
        value: record[item.key],
      }))
    : Object.entries(record).map(([key, itemValue]) => ({
        key,
        label: humanize(key),
        value: itemValue,
      }));
  const updateRecord = (next: WorkspaceRow) => onChange(JSON.stringify(next));

  return (
    <fieldset
      id={id}
      aria-labelledby={labelledBy}
      className="grid gap-3 rounded-xl border border-line bg-panel p-3"
    >
      <legend className="sr-only">{field.label}</legend>
      {entries.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line px-4 py-5 text-center text-xs font-normal text-muted">
          No values configured.
        </p>
      ) : null}
      {entries.map((entry) => (
        <div
          key={entry.key}
          className="grid gap-2 sm:grid-cols-[9rem_1fr_auto] sm:items-end"
        >
          {configuredFields ? (
            <label className="grid gap-1.5 text-[.68rem] font-bold sm:col-span-2">
              {entry.label}
              {entry.type === "textarea" ? (
                <textarea
                  value={structuredInputValue(entry.value)}
                  placeholder={entry.placeholder}
                  onChange={(event) =>
                    updateRecord({ ...record, [entry.key]: event.target.value })
                  }
                  className="min-h-24 resize-y rounded-lg border border-line bg-paper p-3 text-xs leading-5 font-normal outline-none focus:border-ink/25"
                />
              ) : (
                <input
                  type={entry.type ?? "text"}
                  value={structuredInputValue(entry.value)}
                  placeholder={entry.placeholder}
                  onChange={(event) =>
                    updateRecord({ ...record, [entry.key]: event.target.value })
                  }
                  className="min-h-11 rounded-lg border border-line bg-paper px-3 text-xs font-normal outline-none focus:border-ink/25"
                />
              )}
            </label>
          ) : (
            <>
              <label className="grid gap-1.5 text-[.68rem] font-bold">
                Name
                <input
                  value={entry.key}
                  onChange={(event) => {
                    const next = { ...record };
                    delete next[entry.key];
                    if (event.target.value.trim()) {
                      next[event.target.value.trim()] = entry.value;
                    }
                    updateRecord(next);
                  }}
                  className="min-h-11 rounded-lg border border-line bg-paper px-3 text-xs font-normal outline-none focus:border-ink/25"
                />
              </label>
              <label className="grid gap-1.5 text-[.68rem] font-bold">
                Value
                <input
                  value={structuredInputValue(entry.value)}
                  onChange={(event) =>
                    updateRecord({
                      ...record,
                      [entry.key]: event.target.value,
                    })
                  }
                  className="min-h-11 rounded-lg border border-line bg-paper px-3 text-xs font-normal outline-none focus:border-ink/25"
                />
              </label>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label={`Remove ${entry.label}`}
                onClick={() => {
                  const next = { ...record };
                  delete next[entry.key];
                  updateRecord(next);
                }}
              >
                <Trash2 className="size-4 text-red-700" />
              </Button>
            </>
          )}
        </div>
      ))}
      {!configuredFields ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="justify-self-start"
          onClick={() => {
            let index = entries.length + 1;
            let key = `field_${index}`;
            while (key in record) {
              index += 1;
              key = `field_${index}`;
            }
            updateRecord({ ...record, [key]: "" });
          }}
        >
          <CirclePlus className="size-4" /> Add field
        </Button>
      ) : null}
    </fieldset>
  );
}

function initialFieldValue(
  field: WorkspaceField,
  row?: WorkspaceRow,
): FormValue {
  let value =
    (row && field.valueFromRow ? field.valueFromRow(row) : row?.[field.key]) ??
    field.defaultValue ??
    "";
  if (field.key === "media_asset_ids" && row && Array.isArray(row.items)) {
    value = (row.items as WorkspaceRow[])
      .map((item) => item.media_asset_id)
      .join(", ");
  }
  if (field.type === "checkbox") return Boolean(value);
  if (field.type === "multiselect" || field.media?.multiple) {
    if (Array.isArray(value)) return value.map(String);
    if (typeof value === "string") {
      return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return [];
  }
  if (field.type === "json") {
    if (typeof value === "string") {
      try {
        return JSON.stringify(JSON.parse(value), null, 2);
      } catch {
        return value;
      }
    }
    return JSON.stringify(
      value || (field.defaultValue === "[]" ? [] : {}),
      null,
      2,
    );
  }
  if (field.type === "list" && Array.isArray(value)) return value.join(", ");
  if (field.type === "datetime-local" && typeof value === "string")
    return value.slice(0, 16);
  return value == null ? "" : String(value);
}

function parseFieldValue(field: WorkspaceField, value: FormValue): unknown {
  if (field.type === "checkbox") return Boolean(value);
  if (field.type === "multiselect" || field.media?.multiple) {
    return Array.isArray(value) ? value : [];
  }
  const text = String(value).trim();
  if (!text) return field.emptyValue !== undefined ? field.emptyValue : null;
  if (field.type === "number") {
    const parsed = Number(text);
    if (!Number.isFinite(parsed))
      throw new Error(`${field.label} must be a number`);
    return parsed;
  }
  if (field.type === "json") {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      throw new Error(`${field.label} must contain valid JSON`);
    }
  }
  if (field.type === "list") {
    return text
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (field.type === "datetime-local") return new Date(text).toISOString();
  return text;
}

function MutationForm({
  config,
  mutation,
  mode,
  row,
  permissions,
  deliveryAvailable = true,
  onSaved,
  close,
  cancelLabel = "Cancel",
}: {
  config: WorkspaceConfig;
  mutation: WorkspaceMutation;
  mode: "create" | "edit";
  row?: WorkspaceRow;
  permissions: string[];
  deliveryAvailable?: boolean;
  onSaved?: (row: WorkspaceRow) => void;
  close: () => void;
  cancelLabel?: string;
}) {
  const queryClient = useQueryClient();
  const configuredFields = fieldsFor(
    mutation,
    mode,
    permissions,
    deliveryAvailable,
  ).map(
    (field) =>
      field.optionsFor
        ? { ...field, options: field.optionsFor(permissions) }
        : field,
  );
  const [values, setValues] = useState<FormValues>(() =>
    Object.fromEntries(
      configuredFields.map((field) => [
        field.key,
        initialFieldValue(field, row),
      ]),
    ),
  );
  const fields = configuredFields.map((field) =>
    field.optionsForValues
      ? { ...field, options: field.optionsForValues(values) }
      : field,
  );
  const [busyFields, setBusyFields] = useState<string[]>([]);

  const updateFieldValue = (field: WorkspaceField, nextValue: FormValue) => {
    setValues((current) => {
      const next = { ...current, [field.key]: nextValue };
      if (
        config.queryKey !== "documents" ||
        field.key !== "category" ||
        typeof nextValue !== "string"
      ) {
        return next;
      }
      const selectedAudiences = Array.isArray(current.audiences)
        ? current.audiences.map(String)
        : [];
      return {
        ...next,
        audiences: documentAudiencesForCategory(nextValue, selectedAudiences),
      };
    });
  };

  const save = useMutation({
    mutationFn: async () => {
      if (busyFields.length) {
        throw new Error(
          "Wait for the file upload and security check to finish",
        );
      }
      const missingField = fields.find((field) => {
        if (!field.required) return false;
        const value = values[field.key];
        return Array.isArray(value)
          ? value.length === 0
          : value == null || String(value).trim() === "";
      });
      if (missingField) {
        throw new Error(`${missingField.label} is required`);
      }
      if (mutation.clientOnly) {
        return null;
      }
      let payload = Object.fromEntries(
        fields.map((field) => [
          field.key,
          parseFieldValue(field, values[field.key] ?? ""),
        ]),
      );
      if (mutation.prepare) payload = mutation.prepare(payload, row);
      return api<unknown>(endpointFor(mutation, row), {
        method: mutation.method ?? "POST",
        headers: row && mutation.headers ? mutation.headers(row) : undefined,
        body: payload,
      });
    },
    onSuccess: async (result) => {
      const savedRow = workspaceRowFromMutationResult(result);
      toast.success(mutation.successMessage);
      await queryClient.invalidateQueries({ queryKey: [config.queryKey] });
      if (onSaved && savedRow) {
        onSaved(savedRow);
        return;
      }
      close();
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Could not save"),
  });

  return (
    <div>
      <div className="flex items-start justify-between gap-5">
        <div>
          <p className="eyebrow text-coral">
            {mode === "create"
              ? mutation.clientOnly
                ? "Upload"
                : "Create record"
              : "Update record"}
          </p>
          <h2 className="display-type mt-3 text-3xl sm:text-4xl">
            {mutation.label}
          </h2>
          <p className="mt-2 text-xs leading-5 text-muted">
            Required fields are marked. Changes are recorded in the audit
            ledger.
          </p>
        </div>
        <Button
          size="icon"
          variant="ghost"
          onClick={close}
          aria-label="Close form"
        >
          <X className="size-5" />
        </Button>
      </div>
      <form
        className="mt-8 grid gap-5 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {fields.map((field, index) => {
          if (field.hidden) return null;
          const value =
            values[field.key] ?? (field.type === "checkbox" ? false : "");
          const wide =
            ["textarea", "richtext", "json"].includes(field.type ?? "") ||
            field.help ||
            field.prominent ||
            field.type === "media";
          const fieldId = `workspace-${mode}-${field.key}`;
          const labelId = `${fieldId}-label`;
          return (
            <div
              key={field.key}
              className={`grid content-start gap-2 text-xs font-bold ${wide ? "sm:col-span-2" : ""}`}
            >
              <label id={labelId} htmlFor={fieldId}>
                {field.label}
                {field.required ? (
                  <span className="ml-1 text-coral" aria-hidden="true">
                    *
                  </span>
                ) : null}
              </label>
              {field.type === "checkbox" ? (
                <label
                  htmlFor={fieldId}
                  className="flex min-h-12 items-center gap-3 rounded-xl border border-line bg-panel px-4"
                >
                  <input
                    id={fieldId}
                    type="checkbox"
                    checked={Boolean(value)}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [field.key]: event.target.checked,
                      }))
                    }
                    className="size-4 accent-sky"
                  />
                  <span className="font-normal text-muted">
                    {field.checkboxLabel ?? "Enabled"}
                  </span>
                </label>
              ) : field.type === "json" ? (
                <WorkspaceStructuredEditor
                  id={fieldId}
                  labelledBy={labelId}
                  field={field}
                  value={value}
                  onChange={(nextValue) =>
                    setValues((current) => ({
                      ...current,
                      [field.key]: nextValue,
                    }))
                  }
                />
              ) : field.type === "textarea" ? (
                <textarea
                  id={fieldId}
                  autoFocus={index === 0}
                  required={field.required}
                  value={String(value)}
                  placeholder={field.placeholder}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                  className="min-h-32 rounded-xl border border-line bg-panel p-4 text-sm font-normal outline-none focus:border-ink/25"
                />
              ) : field.type === "richtext" ? (
                <RichTextEditor
                  id={fieldId}
                  labelledBy={labelId}
                  required={field.required}
                  value={String(value)}
                  placeholder={
                    field.placeholder ?? `Write ${field.label.toLowerCase()}…`
                  }
                  onChange={(nextValue) =>
                    setValues((current) => ({
                      ...current,
                      [field.key]: nextValue,
                    }))
                  }
                />
              ) : field.type === "media" ? (
                <WorkspaceMediaField
                  field={field}
                  value={Array.isArray(value) ? value : String(value)}
                  downloadBlockedIds={
                    field.media?.downloadControl
                      ? Array.isArray(values.blocked_download_media_ids)
                        ? values.blocked_download_media_ids.map(String)
                        : []
                      : undefined
                  }
                  onBusyChange={(busy) =>
                    setBusyFields((current) =>
                      busy
                        ? [...new Set([...current, field.key])]
                        : current.filter((key) => key !== field.key),
                    )
                  }
                  onChange={(nextValue) =>
                    setValues((current) => {
                      const next = {
                        ...current,
                        [field.key]: nextValue,
                      };
                      if (field.media?.downloadControl) {
                        const selected = Array.isArray(nextValue)
                          ? nextValue.map(String)
                          : nextValue
                            ? [String(nextValue)]
                            : [];
                        const blocked = new Set(
                          (Array.isArray(current.blocked_download_media_ids)
                            ? current.blocked_download_media_ids
                            : []
                          ).map(String),
                        );
                        next.blocked_download_media_ids = selected.filter(
                          (id) => blocked.has(id),
                        );
                      }
                      return next;
                    })
                  }
                  onDownloadBlockedChange={
                    field.media?.downloadControl
                      ? (ids) =>
                          setValues((current) => ({
                            ...current,
                            blocked_download_media_ids: ids,
                          }))
                      : undefined
                  }
                  picker={
                    field.media?.multiple ? (
                      <WorkspaceMultiSelect
                        id={fieldId}
                        labelledBy={labelId}
                        field={field}
                        value={value}
                        onChange={(nextValue) =>
                          setValues((current) => {
                            const next = {
                              ...current,
                              [field.key]: nextValue,
                            };
                            if (field.media?.downloadControl) {
                              const selected = Array.isArray(nextValue)
                                ? nextValue.map(String)
                                : [];
                              const blocked = new Set(
                                (Array.isArray(
                                  current.blocked_download_media_ids,
                                )
                                  ? current.blocked_download_media_ids
                                  : []
                                ).map(String),
                              );
                              next.blocked_download_media_ids = selected.filter(
                                (id) => blocked.has(id),
                              );
                            }
                            return next;
                          })
                        }
                      />
                    ) : (
                      <WorkspaceSelect
                        id={fieldId}
                        labelledBy={labelId}
                        field={field}
                        value={value}
                        autoFocus={index === 0}
                        onChange={(nextValue) =>
                          setValues((current) => ({
                            ...current,
                            [field.key]: nextValue,
                          }))
                        }
                      />
                    )
                  }
                />
              ) : field.type === "select" ? (
                <WorkspaceSelect
                  id={fieldId}
                  labelledBy={labelId}
                  field={field}
                  value={value}
                  autoFocus={index === 0}
                  onChange={(nextValue) => updateFieldValue(field, nextValue)}
                />
              ) : field.type === "multiselect" ? (
                <WorkspaceMultiSelect
                  id={fieldId}
                  labelledBy={labelId}
                  field={field}
                  value={value}
                  onChange={(nextValue) =>
                    setValues((current) => ({
                      ...current,
                      [field.key]: nextValue,
                    }))
                  }
                />
              ) : (
                <input
                  id={fieldId}
                  autoFocus={index === 0}
                  required={field.required}
                  type={field.type === "list" ? "text" : (field.type ?? "text")}
                  step={field.type === "number" ? "any" : undefined}
                  value={String(value)}
                  placeholder={field.placeholder}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                  className={
                    field.prominent
                      ? "min-h-15 rounded-xl border border-line bg-panel px-5 text-base font-semibold outline-none focus:border-ink/25"
                      : "min-h-12 rounded-xl border border-line bg-panel px-4 text-sm font-normal outline-none focus:border-ink/25"
                  }
                />
              )}
              {field.help ? (
                <span className="font-normal leading-5 text-muted">
                  {field.help}
                </span>
              ) : null}
            </div>
          );
        })}
        <div className="mt-3 flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="outline" onClick={close}>
            {cancelLabel}
          </Button>
          <Button
            disabled={save.isPending || busyFields.length > 0}
            className={
              mutation.danger
                ? "bg-red-700 text-white hover:bg-red-800"
                : undefined
            }
          >
            {save.isPending || busyFields.length > 0 ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : mode === "create" ? (
              <CirclePlus className="size-4" />
            ) : (
              <Pencil className="size-4" />
            )}
            {busyFields.length
              ? "Checking upload…"
              : (mutation.submitLabel ??
                (mode === "create" ? mutation.label : "Save changes"))}
          </Button>
        </div>
      </form>
    </div>
  );
}

type WorkspacePanel =
  | { view: "details"; row: WorkspaceRow }
  | { view: "preview"; row: WorkspaceRow; previewKind: WorkspacePreviewKind }
  | { view: "edit"; row: WorkspaceRow; mutation: WorkspaceMutation }
  | { view: "create"; mutation: WorkspaceMutation };

export function WorkspaceClient({
  config,
  headerAction,
  embedded = false,
}: {
  config: WorkspaceConfig;
  headerAction?: React.ReactNode;
  /** Hide the full page title when nested inside a tabbed hub. */
  embedded?: boolean;
}) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [panel, setPanel] = useState<WorkspacePanel | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sort, setSort] = useState<{
    key: string;
    direction: "asc" | "desc";
  }>();
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search);
  const queryEndpoint = workspaceEndpoint(
    config,
    page,
    debouncedSearch,
    filters,
  );

  const selected = panel && panel.view !== "create" ? panel.row : null;

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
  const deliveryOn = isDeliveryAvailable(
    capabilities.data ?? defaultDeliveryCapabilities,
  );
  const query = useQuery({
    queryKey: [config.queryKey, "workspace", queryEndpoint],
    queryFn: () => api<unknown>(queryEndpoint),
  });
  const action = useMutation({
    mutationFn: async ({
      mutation,
      row,
    }: {
      mutation: WorkspaceMutation;
      row: WorkspaceRow;
    }) =>
      api(endpointFor(mutation, row), { method: mutation.method ?? "POST" }),
    onSuccess: async (data, variables) => {
      const apiMessage =
        data &&
        typeof data === "object" &&
        "message" in data &&
        typeof (data as { message: unknown }).message === "string"
          ? (data as { message: string }).message
          : null;
      toast.success(apiMessage ?? variables.mutation.successMessage);
      await queryClient.invalidateQueries({ queryKey: [config.queryKey] });
      setPanel(null);
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Action failed"),
  });

  const permissions = user.data?.permissions ?? [];
  const can = (permission: string) => permissions.includes(permission);
  const visibleFilters = useMemo(() => {
    const filters = config.filters ?? [];
    if (
      config.queryKey === "events" &&
      !(user.data?.permissions ?? []).includes("events.manage")
    ) {
      return filters.filter((filter) => filter.key !== "publication_status");
    }
    return filters;
  }, [config.filters, config.queryKey, user.data?.permissions]);
  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const result = rowsFrom(query.data).filter((row) => {
      if (
        needle &&
        !config.serverPagination?.searchParam &&
        !Object.values(row).some((value) =>
          display(value).toLowerCase().includes(needle),
        )
      ) {
        return false;
      }
      return Object.entries(filters).every(([key, expected]) => {
        if (!expected) return true;
        if (config.serverPagination?.filterParams?.[key]) return true;
        return workspaceFilterMatches(row[key], expected);
      });
    });
    if (!sort) return result;
    return [...result].sort((left, right) => {
      const a = left[sort.key];
      const b = right[sort.key];
      const comparison =
        typeof a === "number" && typeof b === "number"
          ? a - b
          : display(a, sort.key).localeCompare(display(b, sort.key), "en", {
              numeric: true,
              sensitivity: "base",
            });
      return sort.direction === "asc" ? comparison : -comparison;
    });
  }, [config.serverPagination, filters, query.data, search, sort]);

  const serverPage = config.serverPagination ? pageResponse(query.data) : null;
  const pageCount = serverPage
    ? Math.max(1, serverPage.pages)
    : Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visibleRows = config.serverPagination
    ? rows
    : rows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const recordTotal = serverPage?.total ?? rows.length;
  useEffect(() => {
    if (!panel) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (panel.view === "edit") {
        setPanel({ view: "details", row: panel.row });
        return;
      }
      setPanel(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [panel]);

  const detailFields = useMemo(() => workspaceDetailFields(config), [config]);
  const curatedDetails = useMemo(() => {
    if (!selected || !config.detail) return null;
    return visibleDetailEntries(
      selected,
      config.detail,
      user.data?.permissions ?? [],
    );
  }, [selected, config.detail, user.data?.permissions]);
  const detailTitleKey =
    config.detail?.titleKey ?? config.columns[0]?.key ?? "id";
  const detailNoun = config.detail?.noun ?? "Record";

  function closePanel() {
    setPanel(null);
  }

  function openDetails(row: WorkspaceRow) {
    setPanel({ view: "details", row });
  }

  function openEditor(row: WorkspaceRow, mutation: WorkspaceMutation) {
    setPanel({ view: "edit", row, mutation });
  }

  function toggleSort(key: string) {
    setSort((current) =>
      current?.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    );
  }

  function exportRecords() {
    if (!config.exportUrl) return;
    window.open(
      `${API_URL}${config.exportUrl}`,
      "_blank",
      "noopener,noreferrer",
    );
  }

  function runAction(mutation: WorkspaceMutation, row: WorkspaceRow) {
    if (mutation.confirm && !window.confirm(mutation.confirm)) return;
    if (mutation.openMode === "panel" && mutation.previewKind) {
      setPanel({ view: "preview", row, previewKind: mutation.previewKind });
      return;
    }
    if (mutation.open || mutation.openMode === "tab") {
      window.open(
        mutation.href
          ? mutation.href(row)
          : `${API_URL}${endpointFor(mutation, row)}`,
        "_blank",
        "noopener,noreferrer",
      );
      return;
    }
    action.mutate({ mutation, row });
  }

  function handleRowMutation(row: WorkspaceRow, mutation: WorkspaceMutation) {
    if (mutation.fields?.length) {
      openEditor(row, mutation);
      return;
    }
    runAction(mutation, row);
  }

  const selectedActions = selected
    ? rowActionsFor(selected, config, permissions, user.data?.id, deliveryOn)
    : null;

  const actions = (
    <div className="flex shrink-0 flex-wrap gap-2">
      {headerAction}
      {config.exportUrl &&
      can(config.exportPermission ?? "members.export") ? (
        <Button variant="outline" onClick={exportRecords}>
          <ArrowDownToLine className="size-4" /> Export
        </Button>
      ) : null}
      {config.create && can(config.create.permission) ? (
        <Button
          onClick={() =>
            setPanel({ mutation: config.create!, view: "create" })
          }
        >
          <CirclePlus className="size-4" /> {config.create.label}
        </Button>
      ) : null}
    </div>
  );

  return (
    <div className="grid gap-5">
      {embedded ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-3xl text-sm leading-6 text-muted">
            {config.description}
          </p>
          {actions}
        </div>
      ) : (
        <header className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow text-coral">Live workspace</p>
            <h2 className="display-type mt-3 text-4xl sm:text-5xl">
              {config.title}
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              {config.description}
            </p>
          </div>
          {actions}
        </header>
      )}

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-3 sm:flex-row sm:items-center">
          <label className="flex min-h-11 flex-1 items-center gap-3 rounded-xl bg-ink/[.035] px-3">
            <Search className="size-4 text-muted" />
            <span className="sr-only">Search {config.title}</span>
            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder={`Search ${config.title.toLowerCase()}`}
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          <div className="flex gap-2">
            {visibleFilters.length ? (
              <Button
                size="sm"
                variant={filtersOpen ? "outline" : "ghost"}
                onClick={() => setFiltersOpen((value) => !value)}
              >
                <Filter className="size-4" /> Filters
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => query.refetch()}
              disabled={query.isFetching}
            >
              <RefreshCw
                className={`size-4 ${query.isFetching ? "animate-spin" : ""}`}
              />{" "}
              Refresh
            </Button>
          </div>
        </div>

        {filtersOpen && visibleFilters.length ? (
          <div className="flex flex-wrap items-end gap-3 border-b border-line bg-ink/[.015] p-4">
            {visibleFilters.map((filter) => (
              <label
                key={filter.key}
                className="grid min-w-40 gap-1.5 text-[.65rem] font-black uppercase"
              >
                {filter.label}
                <select
                  value={filters[filter.key] ?? ""}
                  onChange={(event) => {
                    setPage(1);
                    setFilters((current) => ({
                      ...current,
                      [filter.key]: event.target.value,
                    }));
                  }}
                  className="min-h-10 rounded-lg border border-line bg-panel px-3 text-xs font-normal normal-case outline-none"
                >
                  <option value="">All</option>
                  {filter.options.map((option) => (
                    <option key={option} value={option}>
                      {humanize(option)}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setPage(1);
                setFilters({});
              }}
            >
              Clear
            </Button>
          </div>
        ) : null}

        {query.isLoading ? (
          <div className="grid gap-3 p-5">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="h-12 animate-pulse rounded-xl bg-ink/5"
              />
            ))}
          </div>
        ) : query.error ? (
          <div className="p-16 text-center">
            <p className="font-black">This workspace could not be loaded.</p>
            <p className="mt-2 text-xs text-muted">
              Check your access or reconnect, then try again.
            </p>
            <button
              className="mt-3 text-sm font-bold text-coral"
              onClick={() => query.refetch()}
            >
              Try again
            </button>
          </div>
        ) : rows.length === 0 ? (
          <div className="p-16 text-center">
            <p className="font-black">No records found</p>
            <p className="mt-2 text-xs text-muted">
              {config.create && can(config.create.permission)
                ? "Change the search or add the first record."
                : "Nothing here yet. Try a different search or check back later."}
            </p>
          </div>
        ) : config.layout === "grid" ? (
          <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">
            {visibleRows.map((row, index) => {
              const rowActions = rowActionsFor(
                row,
                config,
                permissions,
                user.data?.id,
                deliveryOn,
              );
              const titleKey = config.columns[0]?.key ?? "title";
              const metaColumns = config.columns.slice(1);
              return (
                <article
                  key={String(row.id ?? row.key ?? index)}
                  className="group overflow-hidden rounded-2xl border border-line bg-panel text-left shadow-[0_8px_24px_rgba(12,25,48,.04)] transition hover:-translate-y-0.5 hover:shadow-lg"
                >
                  <button
                    type="button"
                    className="w-full text-left"
                    onClick={() => openDetails(row)}
                  >
                    <RecordCardMedia
                      row={row}
                      aspect={config.gridAspect ?? "landscape"}
                    />
                    <div className="grid gap-3 p-4">
                      <div className="min-w-0">
                        <h3 className="text-sm font-black leading-5 break-words">
                          {display(row[titleKey], titleKey)}
                        </h3>
                        {metaColumns.length ? (
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {metaColumns.map((column) => {
                              const value = row[column.key];
                              if (
                                value == null ||
                                value === "" ||
                                column.key === "media_name"
                              ) {
                                return null;
                              }
                              if (
                                column.key === "is_private" &&
                                value !== true &&
                                value !== "true"
                              ) {
                                return null;
                              }
                              const chipLabel =
                                column.key === "is_private"
                                  ? "Private"
                                  : column.key === "content_type" &&
                                      typeof value === "string"
                                    ? value.split("/").pop() || value
                                    : `${column.label}: ${display(value, column.key)}`;
                              return (
                                <span
                                  key={column.key}
                                  className={
                                    statusField(column.key)
                                      ? `inline-flex rounded-full px-2.5 py-1 text-[.62rem] font-bold ${statusClass(value)}`
                                      : "inline-flex rounded-full bg-ink/5 px-2.5 py-1 text-[.62rem] font-bold text-muted"
                                  }
                                >
                                  {chipLabel}
                                </span>
                              );
                            })}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </button>
                  <div className="border-t border-line px-4 py-3">
                    <WorkspaceRowActions
                      actions={rowActions}
                      pending={action.isPending}
                      onView={() => openDetails(row)}
                      onMutation={(mutation) =>
                        handleRowMutation(row, mutation)
                      }
                      onEdit={() => openEditor(row, rowActions.update!)}
                      onArchive={() => runAction(rowActions.archive!, row)}
                      compact
                    />
                  </div>
                </article>
              );
            })}
          </div>
        ) : config.columns.length === 0 ? (
          <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">
            {visibleRows.map((row, index) => {
              const rowActions = rowActionsFor(
                row,
                config,
                permissions,
                user.data?.id,
                deliveryOn,
              );
              return (
                <div
                  key={String(row.id ?? row.key ?? index)}
                  className="rounded-2xl border border-line bg-panel p-5 text-left transition hover:-translate-y-0.5 hover:shadow-lg"
                >
                  <button
                    type="button"
                    className="w-full text-left"
                    onClick={() => openDetails(row)}
                  >
                    <span className="text-[.62rem] font-black tracking-wide text-coral uppercase">
                      {humanize(String(row.group ?? "Metric"))}
                    </span>
                    <b className="mt-2 block text-sm">
                      {humanize(String(row.key ?? "Value"))}
                    </b>
                    <span className="mt-3 block text-2xl font-black">
                      {display(row.value, String(row.key ?? "value"))}
                    </span>
                  </button>
                  <div className="mt-4 border-t border-line pt-3">
                    <WorkspaceRowActions
                      actions={rowActions}
                      pending={action.isPending}
                      onView={() => openDetails(row)}
                      onMutation={(mutation) =>
                        handleRowMutation(row, mutation)
                      }
                      onEdit={() => openEditor(row, rowActions.update!)}
                      onArchive={() => runAction(rowActions.archive!, row)}
                      compact
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="scrollbar-subtle overflow-x-auto">
            <table className="w-full min-w-[46rem] border-collapse text-left">
              <thead>
                <tr className="border-b border-line bg-ink/[.018]">
                  {config.columns.map((column) => (
                    <th key={column.key} className="px-5 py-3">
                      <button
                        className="inline-flex items-center gap-1.5 text-[.62rem] font-black tracking-[.1em] text-muted uppercase hover:text-ink"
                        onClick={() => toggleSort(column.key)}
                      >
                        {column.label}
                        <ArrowUpDown className="size-3" />
                      </button>
                    </th>
                  ))}
                  <th className="px-5 py-3 text-right text-[.62rem] font-black tracking-[.1em] text-muted uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {visibleRows.map((row, index) => {
                  const rowActions = rowActionsFor(
                    row,
                    config,
                    permissions,
                    user.data?.id,
                    deliveryOn,
                  );
                  return (
                    <tr
                      key={String(row.id ?? row.key ?? index)}
                      className="cursor-pointer transition hover:bg-ink/[.025]"
                      onClick={() => openDetails(row)}
                    >
                      {config.columns.map((column) => {
                        const value = row[column.key];
                        const statusLike = statusField(column.key);
                        return (
                          <td
                            key={column.key}
                            className="max-w-xs px-5 py-4 text-xs"
                          >
                            <span
                              className={
                                statusLike
                                  ? `inline-flex rounded-full px-2.5 py-1 text-[.62rem] font-bold ${statusClass(value)}`
                                  : column.key === config.columns[0]?.key
                                    ? "font-black"
                                    : "text-muted"
                              }
                            >
                              {column.key === config.columns[0]?.key ? (
                                <span className="flex items-center gap-3">
                                  <RecordThumbnail row={row} />
                                  <ValueDisplay
                                    value={value}
                                    fieldKey={column.key}
                                    compact
                                  />
                                </span>
                              ) : (
                                <ValueDisplay
                                  value={value}
                                  fieldKey={column.key}
                                  compact
                                />
                              )}
                            </span>
                          </td>
                        );
                      })}
                      <td className="px-4 py-3">
                        <WorkspaceRowActions
                          actions={rowActions}
                          pending={action.isPending}
                          onView={() => openDetails(row)}
                          onMutation={(mutation) =>
                            handleRowMutation(row, mutation)
                          }
                          onEdit={() => openEditor(row, rowActions.update!)}
                          onArchive={() =>
                            runAction(rowActions.archive!, row)
                          }
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3 text-[.65rem] text-muted">
          <span>
            {recordTotal} record{recordTotal === 1 ? "" : "s"} · Updated live
          </span>
          {pageCount > 1 ? (
            <div className="flex items-center gap-2">
              <Button
                size="icon"
                variant="ghost"
                disabled={currentPage === 1}
                onClick={() => setPage(Math.max(1, currentPage - 1))}
                aria-label="Previous page"
              >
                <ChevronLeft className="size-4" />
              </Button>
              <span>
                Page {currentPage} of {pageCount}
              </span>
              <Button
                size="icon"
                variant="ghost"
                disabled={currentPage === pageCount}
                onClick={() => setPage(Math.min(pageCount, currentPage + 1))}
                aria-label="Next page"
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          ) : null}
        </div>
      </Card>

      {panel ? (
        <div
          className="fixed inset-0 z-[90] grid place-items-center bg-black/40 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target !== event.currentTarget) return;
            if (panel.view === "edit" || panel.view === "preview") {
              setPanel({ view: "details", row: panel.row });
              return;
            }
            closePanel();
          }}
          role="presentation"
        >
          <section
            className={`flex max-h-[90vh] w-full flex-col overflow-hidden rounded-3xl border border-line bg-paper shadow-2xl ${
              panel.view === "preview" ? "max-w-4xl" : "max-w-2xl"
            }`}
            onMouseDown={(event) => event.stopPropagation()}
            aria-label={
              panel.view === "details"
                ? `${detailNoun} details`
                : panel.view === "preview"
                  ? `${detailNoun} preview`
                  : panel.mutation.label
            }
            aria-modal="true"
            role="dialog"
          >
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-6 sm:p-8">
              {panel.view === "details" ? (
                selectedActions ? (
                  <RecordDetailsView
                    noun={detailNoun}
                    title={display(panel.row[detailTitleKey], detailTitleKey)}
                    subtitle={
                      config.detail?.subtitleKeys?.length
                        ? config.detail.subtitleKeys
                            .map((key) => display(panel.row[key], key))
                            .filter((value) => value !== "Not provided")
                            .join(" · ") || undefined
                        : undefined
                    }
                    images={recordImages(panel.row)}
                    entries={(curatedDetails
                      ? curatedDetails.map(({ field, value }) => ({
                          key: field.key,
                          label: field.label,
                          value,
                          richtext: field.format === "richtext",
                          format: field.format,
                        }))
                      : Object.entries(panel.row)
                          .filter(
                            ([key]) =>
                              !key.startsWith("_") &&
                              !isTechnicalField(key) &&
                              key !== detailTitleKey,
                          )
                          .map(([key, value]) => {
                            const field = detailFields.get(key);
                            return {
                              key,
                              label: field?.label ?? humanize(key),
                              value,
                              richtext: field?.type === "richtext",
                            };
                          })
                    ).filter((entry) => {
                      if (config.detail?.hideEmpty === false) return true;
                      if (entry.value == null || entry.value === "")
                        return false;
                      if (
                        typeof entry.value === "string" &&
                        !entry.value.trim()
                      ) {
                        return false;
                      }
                      return true;
                    })}
                    primaryActions={selectedActions.primary}
                    secondaryActions={selectedActions.secondary}
                    canUpdate={selectedActions.canUpdate}
                    canArchive={selectedActions.canArchive}
                    updateLabel={selectedActions.update?.label}
                    archiveLabel={selectedActions.archive?.label}
                    actionPending={action.isPending}
                    onClose={closePanel}
                    onPrimaryAction={(item) =>
                      handleRowMutation(panel.row, item)
                    }
                    onEdit={() =>
                      openEditor(panel.row, selectedActions.update!)
                    }
                    onArchive={() =>
                      runAction(selectedActions.archive!, panel.row)
                    }
                    ValueDisplay={ValueDisplay}
                  />
                ) : null
              ) : panel.view === "preview" ? (
                <div className="grid gap-4">
                  <div className="flex items-start justify-between gap-4">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        setPanel({ view: "details", row: panel.row })
                      }
                    >
                      <ArrowLeft className="size-4" /> Back to details
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={closePanel}
                      aria-label="Close preview"
                    >
                      <X className="size-5" />
                    </Button>
                  </div>
                  <WorkspacePanelPreview
                    kind={panel.previewKind}
                    row={panel.row}
                    onBack={() =>
                      setPanel({ view: "details", row: panel.row })
                    }
                  />
                </div>
              ) : (
                <MutationForm
                  key={`${panel.view}-${panel.mutation.label}-${
                    panel.view === "edit" ? String(panel.row.id) : "new"
                  }`}
                  config={config}
                  mutation={panel.mutation}
                  mode={panel.view === "create" ? "create" : "edit"}
                  row={panel.view === "edit" ? panel.row : undefined}
                  permissions={permissions}
                  deliveryAvailable={deliveryOn}
                  cancelLabel={
                    panel.view === "edit" ? "Back to details" : "Cancel"
                  }
                  onSaved={
                    panel.view === "edit"
                      ? (saved) => setPanel({ view: "details", row: saved })
                      : undefined
                  }
                  close={
                    panel.view === "edit"
                      ? () => setPanel({ view: "details", row: panel.row })
                      : closePanel
                  }
                />
              )}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
