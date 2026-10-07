"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CirclePlus,
  Filter,
  ImageIcon,
  Inbox,
  LoaderCircle,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  Users,
  X,
} from "lucide-react";
import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { WorkspacePanelPreview } from "@/components/dashboard/workspace-panel-preview";
import { RecordDetailsView } from "@/components/dashboard/record-details-view";
import { WorkspaceRowActions } from "@/components/dashboard/workspace-row-actions";
import { RichTextEditor } from "@/components/dashboard/rich-text-editor";
import { WorkspaceMediaField } from "@/components/dashboard/workspace-media-field";
import { GoogleDriveGalleryImport } from "@/components/dashboard/google-drive-gallery-import";
import { API_URL, api } from "@/lib/api";
import {
  defaultDeliveryCapabilities,
  deliveryAvailable as isDeliveryAvailable,
} from "@/lib/delivery-capabilities";
import {
  analyticsSnapshotFrom,
  formatAnalyticsValue,
  type AnalyticsSnapshot,
} from "@/lib/workspace-analytics";
import {
  compactDateLabel,
  display,
  displayChoice,
  displayTitleWithoutDuplicateSubtitle,
} from "@/lib/workspace-display";
import { visibleDetailEntries } from "@/lib/workspace-detail";
import { rowActionsFor } from "@/lib/workspace-row-actions";
import {
  documentAudiencesForCategory,
  nextMultiSelectValue,
  workspaceOptionQueryState,
} from "@/lib/workspace-options";
import {
  workspaceFilterMatches,
  workspaceRowFromMutationResult,
} from "@/lib/workspaces";
import {
  collectionLabel,
  wizardStepIndexForField,
  workspacePresentationFor,
  type WorkspaceWizardStep,
} from "@/lib/workspace-presentation";
import type {
  WorkspaceColumn,
  WorkspaceConfig,
  WorkspaceField,
  WorkspaceMutation,
  WorkspacePreviewKind,
  WorkspaceRow,
} from "@/lib/workspaces";
import {
  cn,
  formatPersonName,
  formatRankForName,
  humanize,
  initials,
  matchCaseStyle,
} from "@/lib/utils";

type FormValue = string | boolean | string[];
type FormValues = Record<string, FormValue>;
type User = { id: string; permissions: string[] };

const SITE_SETTING_LABELS: Record<string, string> = {
  "site.identity": "Site identity",
  "site.contact": "Contact information",
  "site.social": "Social media",
  "site.home": "Homepage introduction",
  "site.about": "About page introduction",
  "site.resources": "Resources introduction",
  "site.footer": "Footer content",
  "site.carousel": "Homepage carousel",
};

const SITE_SETTING_FIELDS: Record<
  string,
  NonNullable<WorkspaceField["structuredFields"]>
> = {
  "site.identity": [
    { key: "name", label: "Association name" },
    { key: "short_name", label: "Short name" },
    { key: "tagline", label: "Tagline" },
  ],
  "site.contact": [
    { key: "email", label: "Public email", type: "email" },
    { key: "phone", label: "Public phone" },
    { key: "address", label: "Office address", type: "textarea" },
    { key: "office_hours", label: "Office hours" },
  ],
  "site.social": [
    { key: "facebook", label: "Facebook URL", type: "url" },
    { key: "x", label: "X / Twitter URL", type: "url" },
    { key: "linkedin", label: "LinkedIn URL", type: "url" },
    { key: "instagram", label: "Instagram URL", type: "url" },
    { key: "youtube", label: "YouTube URL", type: "url" },
  ],
  "site.home": [
    { key: "eyebrow", label: "Section label" },
    { key: "headline", label: "Homepage headline" },
    { key: "introduction", label: "Homepage introduction", type: "textarea" },
  ],
  "site.about": [
    { key: "heading", label: "About heading" },
    { key: "introduction", label: "About introduction", type: "textarea" },
  ],
  "site.resources": [
    { key: "heading", label: "Resources heading" },
    { key: "introduction", label: "Resources introduction", type: "textarea" },
  ],
  "site.footer": [
    { key: "copyright_name", label: "Copyright name" },
    { key: "membership_note", label: "Membership note", type: "textarea" },
  ],
};

type SelectMenuPosition = {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
  placement: "top" | "bottom";
};

type SelectViewportBounds = {
  top: number;
  right: number;
  bottom: number;
  left: number;
};

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

function selectViewportBounds(): SelectViewportBounds {
  const visualViewport = window.visualViewport;
  const top = visualViewport?.offsetTop ?? 0;
  const left = visualViewport?.offsetLeft ?? 0;
  const right = left + (visualViewport?.width ?? window.innerWidth);
  let bottom = top + (visualViewport?.height ?? window.innerHeight);
  const bottomNavigation = document.querySelector<HTMLElement>(
    "[data-dashboard-bottom-nav]",
  );
  const navigationRect = bottomNavigation?.getBoundingClientRect();

  if (
    navigationRect &&
    navigationRect.width > 0 &&
    navigationRect.height > 0 &&
    navigationRect.top > top &&
    navigationRect.top < bottom
  ) {
    bottom = navigationRect.top;
  }

  return { top, right, bottom, left };
}

function selectMenuPositionFor(
  trigger: HTMLElement,
  menuHeight = 320,
): SelectMenuPosition {
  const rect = trigger.getBoundingClientRect();
  const viewport = selectViewportBounds();
  const viewportPadding = 12;
  const gap = 8;
  const viewportWidth = Math.max(
    viewport.right - viewport.left,
    viewportPadding * 2 + 1,
  );
  const width = Math.min(
    Math.max(rect.width, 256),
    viewportWidth - viewportPadding * 2,
  );
  const left = Math.min(
    Math.max(viewport.left + viewportPadding, rect.left),
    Math.max(
      viewport.left + viewportPadding,
      viewport.right - width - viewportPadding,
    ),
  );
  const spaceBelow = Math.max(
    0,
    viewport.bottom - rect.bottom - gap - viewportPadding,
  );
  const spaceAbove = Math.max(
    0,
    rect.top - gap - viewport.top - viewportPadding,
  );
  const measuredHeight = menuHeight > 0 ? menuHeight : 320;
  const usefulHeight = Math.min(measuredHeight, 320);
  const placement =
    spaceBelow >= Math.min(usefulHeight, 224) || spaceBelow >= spaceAbove
      ? "bottom"
      : "top";
  const availableHeight = placement === "bottom" ? spaceBelow : spaceAbove;
  const maxHeight = Math.min(320, availableHeight);
  const renderedHeight = Math.min(measuredHeight, maxHeight);
  const top =
    placement === "bottom"
      ? Math.min(
          rect.bottom + gap,
          viewport.bottom - viewportPadding - renderedHeight,
        )
      : Math.max(
          viewport.top + viewportPadding,
          rect.top - gap - renderedHeight,
        );

  return { top, left, width, maxHeight, placement };
}

function sameSelectMenuPosition(
  current: SelectMenuPosition | null,
  next: SelectMenuPosition,
) {
  return (
    current?.top === next.top &&
    current.left === next.left &&
    current.width === next.width &&
    current.maxHeight === next.maxHeight &&
    current.placement === next.placement
  );
}

function workspaceEndpoint(
  config: WorkspaceConfig,
  page: number,
  search: string,
  filters: Record<string, string>,
  sort?: { key: string; direction: "asc" | "desc" },
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
  if (sort) {
    params.set("sort_by", sort.key);
    params.set("sort_dir", sort.direction);
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
  fallbackOption,
  formValues,
  record,
}: {
  id: string;
  labelledBy: string;
  field: WorkspaceField;
  value: FormValue;
  autoFocus: boolean;
  onChange: (value: string) => void;
  fallbackOption?: { value: string; label: string };
  formValues?: WorkspaceRow;
  record?: WorkspaceRow;
}) {
  const source = field.optionSource;
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [menuPosition, setMenuPosition] = useState<SelectMenuPosition | null>(
    null,
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
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
        .filter(
          (row) =>
            (source.filter?.(row) ?? true) &&
            (source.filterForValues?.(row, formValues ?? {}, record) ?? true),
        )
        .map((row) => ({ value: source.value(row), label: source.label(row) }))
    : [];
  const loadedOptions = source
    ? dynamicOptions
    : (field.options ?? []).map((option) => ({
        value: option,
        label: humanize(option),
      }));
  const options =
    fallbackOption &&
    String(value) === fallbackOption.value &&
    !source?.filterForValues &&
    !loadedOptions.some((option) => option.value === fallbackOption.value)
      ? [fallbackOption, ...loadedOptions]
      : loadedOptions;
  const optionState = workspaceOptionQueryState(Boolean(source), optionsQuery);
  const dependentDisabled =
    source?.disabledForValues?.(formValues ?? {}, record) ?? false;
  const contextualEmptyLabel = source?.emptyLabelForValues?.(
    formValues ?? {},
    record,
  );
  const emptyLabel = optionState.isLoading
    ? "Loading available options…"
    : optionState.isError
      ? "Options unavailable — refresh and try again"
      : source && options.length === 0
        ? (contextualEmptyLabel ?? source.emptyLabel ?? "No options available")
        : "Select";

  const searchable = Boolean(source) || options.length > 10;
  const selectedOption = options.find(
    (option) => option.value === String(value),
  );
  const searchTerm = search.trim().toLowerCase();
  const remoteSearchSettled =
    Boolean(source?.searchParam) && remoteSearch.trim() === search.trim();
  const filteredOptions = options.filter((option) => {
    if (!searchTerm) return true;
    if (remoteSearchSettled && option.value !== fallbackOption?.value) {
      return true;
    }
    return option.label.toLowerCase().includes(searchTerm);
  });
  const selectedFilteredIndex = filteredOptions.findIndex(
    (option) => option.value === String(value),
  );

  const closeMenu = useCallback((restoreFocus = false) => {
    setOpen(false);
    setSearch("");
    setActiveIndex(-1);
    setMenuPosition(null);
    if (restoreFocus) {
      window.requestAnimationFrame(() => triggerRef.current?.focus());
    }
  }, []);

  const updateMenuPosition = useCallback(
    (menuHeight = 320) => {
      const trigger = triggerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const viewport = selectViewportBounds();
      if (rect.bottom < viewport.top || rect.top > viewport.bottom) {
        closeMenu();
        return;
      }
      const next = selectMenuPositionFor(trigger, menuHeight);
      setMenuPosition((current) =>
        sameSelectMenuPosition(current, next) ? current : next,
      );
    },
    [closeMenu],
  );

  useLayoutEffect(() => {
    if (!open) return;
    updateMenuPosition();
  }, [open, updateMenuPosition]);

  useLayoutEffect(() => {
    if (!open || !menuPosition || !menuRef.current) return;
    updateMenuPosition(menuRef.current.offsetHeight);
  }, [filteredOptions.length, menuPosition, open, updateMenuPosition]);

  useEffect(() => {
    if (!open || activeIndex < 0) return;
    menuRef.current
      ?.querySelector<HTMLElement>(`[data-option-index="${activeIndex}"]`)
      ?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex, open]);

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        containerRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      ) {
        return;
      }
      closeMenu();
    };
    const closeOnFocusLeave = (event: FocusEvent) => {
      if (!menuRef.current) return;
      const target = event.target as Node;
      if (
        containerRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      ) {
        return;
      }
      closeMenu();
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      closeMenu(true);
    };
    const reposition = (event: Event) => {
      if (
        event.target instanceof Node &&
        menuRef.current?.contains(event.target)
      ) {
        return;
      }
      updateMenuPosition(menuRef.current?.offsetHeight ?? 320);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("focusin", closeOnFocusLeave);
    document.addEventListener("keydown", closeOnEscape);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    window.visualViewport?.addEventListener("resize", reposition);
    window.visualViewport?.addEventListener("scroll", reposition);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("focusin", closeOnFocusLeave);
      document.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
      window.visualViewport?.removeEventListener("resize", reposition);
      window.visualViewport?.removeEventListener("scroll", reposition);
    };
  }, [closeMenu, open, updateMenuPosition]);

  if (searchable) {
    const disabled =
      dependentDisabled || (Boolean(source) && optionState.isLoading);
    const chooseOption = (nextValue: string) => {
      onChange(nextValue);
      closeMenu(true);
    };
    const menu =
      open && menuPosition && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={menuRef}
              className="fixed z-[100] flex flex-col overflow-hidden rounded-xl border border-line bg-paper shadow-[0_18px_55px_rgba(12,25,48,.18)]"
              data-placement={menuPosition.placement}
              style={{
                top: menuPosition.top,
                left: menuPosition.left,
                width: menuPosition.width,
                maxHeight: menuPosition.maxHeight,
              }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <label className="flex min-h-11 shrink-0 items-center gap-2 border-b border-line px-3">
                <Search className="size-4 shrink-0 text-muted" />
                <span className="sr-only">Search {field.label}</span>
                <input
                  autoFocus
                  value={search}
                  aria-controls={`${id}-options`}
                  aria-activedescendant={
                    activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined
                  }
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setActiveIndex(0);
                  }}
                  onKeyDown={(event) => {
                    if (!filteredOptions.length) return;
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveIndex((current) =>
                        current < filteredOptions.length - 1 ? current + 1 : 0,
                      );
                    } else if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveIndex((current) =>
                        current > 0 && current < filteredOptions.length
                          ? current - 1
                          : filteredOptions.length - 1,
                      );
                    } else if (event.key === "Home") {
                      event.preventDefault();
                      setActiveIndex(0);
                    } else if (event.key === "End") {
                      event.preventDefault();
                      setActiveIndex(filteredOptions.length - 1);
                    } else if (
                      event.key === "Enter" &&
                      activeIndex >= 0 &&
                      activeIndex < filteredOptions.length
                    ) {
                      event.preventDefault();
                      chooseOption(filteredOptions[activeIndex]!.value);
                    }
                  }}
                  placeholder={`Search ${field.label.toLowerCase()}`}
                  className="w-full bg-transparent text-sm font-normal outline-none"
                />
              </label>
              {!field.required && value && !optionState.isLoading ? (
                <button
                  type="button"
                  onClick={() => chooseOption("")}
                  className="flex min-h-10 shrink-0 items-center border-b border-line px-4 text-left text-xs text-muted transition hover:bg-ink/[.04] focus-visible:bg-ink/[.04] focus-visible:outline-none"
                >
                  Clear selection
                </button>
              ) : null}
              <div
                id={`${id}-options`}
                role="listbox"
                aria-labelledby={labelledBy}
                className="scrollbar-subtle min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-contain p-1.5"
              >
                {optionState.isLoading ? (
                  <p
                    className="px-3 py-4 text-center text-xs font-normal text-muted"
                    role="status"
                  >
                    Searching available options…
                  </p>
                ) : optionState.isError ? (
                  <div className="grid justify-items-center gap-2 px-3 py-4 text-center">
                    <p
                      className="text-xs font-normal text-red-700 dark:text-red-300"
                      role="alert"
                    >
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
                ) : null}
                {!optionState.isLoading && !optionState.isError
                  ? filteredOptions.map((option, index) => {
                      const isSelected = option.value === String(value);
                      const isActive = index === activeIndex;
                      return (
                        <button
                          id={`${id}-option-${index}`}
                          key={option.value}
                          type="button"
                          role="option"
                          tabIndex={-1}
                          data-option-index={index}
                          aria-selected={isSelected}
                          onPointerMove={() => setActiveIndex(index)}
                          onClick={() => chooseOption(option.value)}
                          className={cn(
                            "flex min-h-10 w-full items-center justify-between gap-3 rounded-lg px-3 text-left text-xs outline-none transition",
                            isActive ? "bg-ink/[.06]" : "hover:bg-ink/[.04]",
                          )}
                        >
                          <span className="min-w-0 break-words">
                            {option.label}
                          </span>
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
                  <p
                    className="px-3 py-4 text-center text-xs font-normal text-muted"
                    role="status"
                  >
                    {options.length
                      ? "No matching options"
                      : (contextualEmptyLabel ??
                        source?.emptyLabel ??
                        "No options available")}
                  </p>
                ) : null}
              </div>
            </div>,
            document.body,
          )
        : null;

    return (
      <div ref={containerRef} className="relative min-w-0">
        <button
          ref={triggerRef}
          id={id}
          type="button"
          role="combobox"
          aria-labelledby={labelledBy}
          aria-expanded={open}
          aria-controls={`${id}-options`}
          aria-haspopup="listbox"
          autoFocus={autoFocus}
          disabled={disabled}
          onClick={() => {
            if (open) closeMenu();
            else {
              setActiveIndex(
                selectedFilteredIndex >= 0
                  ? selectedFilteredIndex
                  : filteredOptions.length
                    ? 0
                    : -1,
              );
              setOpen(true);
            }
          }}
          onKeyDown={(event) => {
            if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
            event.preventDefault();
            setActiveIndex(
              selectedFilteredIndex >= 0
                ? selectedFilteredIndex
                : filteredOptions.length
                  ? 0
                  : -1,
            );
            setOpen(true);
          }}
          className="workspace-control flex min-h-10 w-full min-w-0 items-center justify-between gap-3 rounded-xl px-4 text-left text-sm font-normal disabled:cursor-not-allowed disabled:opacity-70"
        >
          <span
            className={cn(
              "min-w-0 truncate",
              selectedOption ? "text-ink" : "text-muted",
            )}
          >
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
        {menu}
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
        dependentDisabled ||
        (Boolean(source) &&
          (optionState.isLoading ||
            optionState.isError ||
            options.length === 0))
      }
      onChange={(event) => onChange(event.target.value)}
      className="workspace-control min-h-10 rounded-xl px-4 text-sm font-normal disabled:cursor-not-allowed disabled:opacity-70"
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
      className="workspace-control max-h-64 overflow-y-auto rounded-xl p-2"
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
          <p className="text-xs font-normal text-red-700 dark:text-red-300">
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

function audienceLabel(item: unknown, index: number) {
  if (!item || typeof item !== "object") {
    return displayChoice(item, "audiences");
  }
  const audience = item as WorkspaceRow;
  const type = String(audience.type ?? "");
  const value = String(audience.value ?? "");
  if (type === "general_public") return "General public";
  if (type === "everyone" || type === "all_members") return "All members";
  if (type === "role" && value) {
    const roleLabels: Record<string, string> = {
      member: "Members",
      executive: "Executives",
      editor: "Editors",
      publisher: "Publishers",
      secretary: "Secretaries",
      administrator: "Administrators",
    };
    return roleLabels[value] ?? `${displayChoice(value, "role")} role`;
  }
  if (type === "user") {
    return String(
      audience.full_name ?? audience.email ?? `Selected member ${index + 1}`,
    );
  }
  return objectItemLabel(audience, index);
}

function displayWithPersonCase(
  value: unknown,
  fieldKey: string,
  row?: WorkspaceRow,
) {
  if (fieldKey === "full_name" && typeof value === "string") {
    return formatPersonName(value);
  }
  if (fieldKey === "academic_rank" && typeof value === "string") {
    const name = typeof row?.full_name === "string" ? row.full_name : undefined;
    return formatRankForName(name, value) || display(value, fieldKey);
  }
  if (fieldKey === "title" && typeof value === "string") {
    const name =
      typeof row?.full_name === "string"
        ? row.full_name
        : [row?.other_name, row?.surname].filter(Boolean).join(" ");
    return name
      ? matchCaseStyle(String(name), value)
      : display(value, fieldKey);
  }
  return display(value, fieldKey);
}

export function ValueDisplay({
  value,
  fieldKey,
  compact = false,
  row,
  dateStyle,
}: {
  value: unknown;
  fieldKey: string;
  compact?: boolean;
  row?: WorkspaceRow;
  dateStyle?: WorkspaceColumn["dateStyle"];
}) {
  if (isEmptyValue(value)) {
    return <span className="text-muted">Not provided</span>;
  }
  if (
    fieldKey === "academic_rank" ||
    fieldKey === "full_name" ||
    fieldKey === "title"
  ) {
    return <>{displayWithPersonCase(value, fieldKey, row)}</>;
  }
  if (fieldKey === "key" && typeof value === "string") {
    return (
      <>{SITE_SETTING_LABELS[value] ?? humanize(value.replace(/[.-]/g, " "))}</>
    );
  }
  if (fieldKey === "audiences" && Array.isArray(value)) {
    return (
      <span className="flex flex-wrap gap-1">
        {value.map((item, index) => (
          <span
            key={`${audienceLabel(item, index)}-${index}`}
            className={
              compact
                ? "workspace-table-chip w-fit max-w-full bg-ink/5 text-muted"
                : "rounded-full bg-ink/5 px-2.5 py-1 text-[.68rem] font-semibold"
            }
          >
            {audienceLabel(item, index)}
          </span>
        ))}
      </span>
    );
  }
  if (Array.isArray(value)) {
    if (compact && value.some((item) => typeof item === "object")) {
      return <>{display(value, fieldKey)}</>;
    }
    if (value.every((item) => typeof item !== "object")) {
      return (
        <span className={cn("flex flex-wrap", compact ? "gap-1" : "gap-1.5")}>
          {value.map((item, index) => (
            <span
              key={`${String(item)}-${index}`}
              className={
                compact
                  ? "workspace-table-chip w-fit max-w-full bg-ink/5 text-muted"
                  : "rounded-full bg-ink/5 px-2.5 py-1 text-[.68rem]"
              }
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
  if (compact) {
    const compactDate = compactDateLabel(value, dateStyle ?? "datetime");
    if (compactDate) {
      return <span className="whitespace-nowrap">{compactDate}</span>;
    }
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
  "slug",
  "version",
  "metadata",
  "input_json",
  "result_json",
  "payload",
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

export function recordImages(row: WorkspaceRow): RecordImage[] {
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
    <span className="relative size-7 shrink-0 overflow-hidden rounded-md bg-ink/5">
      <Image
        fill
        unoptimized
        alt=""
        className="object-cover"
        sizes="28px"
        src={`/api/v1/media/${image.id}/content`}
      />
    </span>
  );
}

function isDateField(key: string) {
  return /(_at|_on|_date)$/.test(key) || key === "date";
}

function AnalyticsDashboard({ snapshot }: { snapshot: AnalyticsSnapshot }) {
  return (
    <div className="grid gap-0">
      <div className="grid grid-cols-1 divide-y divide-line border-b border-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {snapshot.groups.map((group) => {
          const headline = group.metrics[0];
          return (
            <div key={group.id} className="min-w-0 px-4 py-3">
              <p className="text-[.6rem] font-semibold tracking-[.08em] text-muted uppercase">
                {group.label}
              </p>
              <p className="mt-1 truncate text-[13px] font-medium tabular-nums text-ink">
                {headline
                  ? `${formatAnalyticsValue(headline.value)} ${headline.label.toLowerCase()}`
                  : "—"}
              </p>
            </div>
          );
        })}
      </div>
      <div className="grid gap-6 p-4 lg:grid-cols-3">
        {snapshot.groups.map((group) => (
          <section key={group.id} className="min-w-0">
            <h2 className="text-[.6rem] font-semibold tracking-[.08em] text-muted uppercase">
              {group.label}
            </h2>
            <dl className="mt-2 divide-y divide-line/80 border-y border-line/80">
              {group.metrics.map((metric) => (
                <div
                  key={metric.key}
                  className="flex items-baseline justify-between gap-4 py-2"
                >
                  <dt className="text-[13px] text-muted">{metric.label}</dt>
                  <dd className="text-[13px] font-medium tabular-nums text-ink">
                    {formatAnalyticsValue(metric.value)}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </div>
  );
}

function DirectoryAvatar({
  row,
  name,
  compact = false,
}: {
  row: WorkspaceRow;
  name: string;
  compact?: boolean;
}) {
  const image = recordImages(row)[0];
  const [broken, setBroken] = useState(false);
  const shell = compact
    ? "relative grid size-7 shrink-0 place-items-center overflow-hidden rounded-full bg-[#0b1a2e] text-paper"
    : "relative grid size-11 shrink-0 place-items-center overflow-hidden rounded-full bg-[#0b1a2e] text-paper";
  if (image && !broken) {
    return (
      <span className={shell}>
        <Image
          fill
          unoptimized
          alt=""
          className="object-cover"
          sizes={compact ? "28px" : "44px"}
          src={`/api/v1/media/${image.id}/content`}
          onError={() => setBroken(true)}
        />
      </span>
    );
  }
  return (
    <span className={shell}>
      <span
        className={
          compact
            ? "text-[.58rem] font-semibold tracking-wide"
            : "text-xs font-semibold tracking-wide"
        }
      >
        {initials(name) || "—"}
      </span>
    </span>
  );
}

function ListEmptyGlyph({ variant }: { variant?: string }) {
  if (variant === "directory") return <Users className="size-5" />;
  if (variant === "media" || variant === "cards") {
    return <ImageIcon className="size-5" />;
  }
  return <Inbox className="size-5" />;
}

function RecordCardMedia({
  row,
  aspect = "landscape",
}: {
  row: WorkspaceRow;
  aspect?: "square" | "landscape";
}) {
  const image = recordImages(row)[0];
  const aspectClass = aspect === "square" ? "aspect-square" : "aspect-[16/10]";
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
        className={`flex ${aspectClass} flex-col items-center justify-center gap-1 bg-[#0b1a2e]/[0.04] px-4 text-center`}
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
      className={`relative ${aspectClass} overflow-hidden bg-ink/5`}
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

function columnSubtitle(column: WorkspaceColumn, row: WorkspaceRow) {
  if (!column.subtitleKey) return null;
  const value = row[column.subtitleKey];
  return isEmptyValue(value) ? null : value;
}

function WorkspaceTableCell({
  column,
  row,
  isPrimary,
}: {
  column: WorkspaceColumn;
  row: WorkspaceRow;
  isPrimary: boolean;
}) {
  const value = row[column.key];
  const subtitle = columnSubtitle(column, row);
  const statusLike = statusField(column.key);
  const metricKeys = column.metricKeys ?? [];

  if (isPrimary) {
    const titleValue = displayTitleWithoutDuplicateSubtitle(value, subtitle);
    return (
      <span className="flex min-w-0 items-center gap-2.5">
        {column.key === "full_name" ? (
          <DirectoryAvatar
            compact
            row={row}
            name={displayWithPersonCase(titleValue, column.key, row)}
          />
        ) : (
          <RecordThumbnail row={row} />
        )}
        <span className="min-w-0">
          <span className="block truncate font-medium text-ink">
            <ValueDisplay
              value={titleValue}
              fieldKey={column.key}
              row={row}
              compact
              dateStyle={column.dateStyle}
            />
          </span>
          {subtitle != null && column.subtitleKey ? (
            <span className="mt-0.5 block truncate text-[12px] font-normal text-muted">
              <ValueDisplay
                value={subtitle}
                fieldKey={column.subtitleKey}
                row={row}
                compact
              />
            </span>
          ) : null}
        </span>
      </span>
    );
  }

  if (metricKeys.length) {
    const parts = [column.key, ...metricKeys].map((key) => ({
      key,
      value: row[key],
    }));
    const label = parts
      .map(
        (part) =>
          `${display(part.value, part.key)} ${humanize(part.key).toLowerCase()}`,
      )
      .join(", ");
    return (
      <span
        className="inline-flex items-baseline justify-end gap-0 tabular-nums"
        aria-label={label}
        title={label}
      >
        {parts.map((part, index) => (
          <span key={part.key} className="inline-flex items-baseline">
            {index > 0 ? (
              <span className="px-1 font-normal text-muted/80">/</span>
            ) : null}
            <span
              className={
                index === 0 ? "font-medium text-ink" : "text-muted"
              }
            >
              {isEmptyValue(part.value) ? "—" : display(part.value, part.key)}
            </span>
          </span>
        ))}
      </span>
    );
  }

  return (
    <span
      className={cn(
        "flex min-w-0 flex-col items-start gap-0.5",
        column.align === "end" && "items-end text-right",
      )}
    >
      <span
        className={
          statusLike
            ? `workspace-table-chip w-fit max-w-full ${statusClass(value)}`
            : "text-[13px] text-muted"
        }
      >
        <ValueDisplay
          value={value}
          fieldKey={column.key}
          row={row}
          compact
          dateStyle={column.dateStyle}
        />
      </span>
      {subtitle != null && column.subtitleKey ? (
        <span className="max-w-[12rem] truncate text-[12px] font-normal text-muted">
          <ValueDisplay
            value={subtitle}
            fieldKey={column.subtitleKey}
            row={row}
            compact
          />
        </span>
      ) : null}
    </span>
  );
}

function settingHighlights(value: unknown) {
  let parsed = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value) as unknown;
    } catch {
      return value.trim() ? [{ key: "value", label: "Value", value }] : [];
    }
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return isEmptyValue(parsed)
      ? []
      : [{ key: "value", label: "Value", value: parsed }];
  }
  return Object.entries(parsed)
    .filter(([, item]) => !isEmptyValue(item))
    .filter(([, item]) => {
      if (!item || typeof item !== "object") return true;
      return (
        Array.isArray(item) && item.every((entry) => typeof entry !== "object")
      );
    })
    .slice(0, 4)
    .map(([key, item]) => ({ key, label: humanize(key), value: item }));
}

export function endpointFor(mutation: WorkspaceMutation, row?: WorkspaceRow) {
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
      if (!deliveryAvailable && mode === "create" && field.key === "staff_id") {
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
                  <Trash2 className="size-4 text-red-700 dark:text-red-300" />
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
                <Trash2 className="size-4 text-red-700 dark:text-red-300" />
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

export function MutationForm({
  config,
  mutation,
  mode,
  row,
  permissions,
  deliveryAvailable = true,
  onSaved,
  close,
  cancelLabel = "Cancel",
  showCloseButton = true,
  steps,
  variant = "dialog",
  draftKey,
  recoverableFields = [],
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
  showCloseButton?: boolean;
  steps?: WorkspaceWizardStep[];
  variant?: "dialog" | "page";
  draftKey?: string;
  recoverableFields?: string[];
}) {
  const queryClient = useQueryClient();
  const configuredFields = fieldsFor(
    mutation,
    mode,
    permissions,
    deliveryAvailable,
  ).map((field) => {
    const permissionField = field.optionsFor
      ? { ...field, options: field.optionsFor(permissions) }
      : field;
    if (
      config.key === "settings" &&
      field.key === "value" &&
      typeof row?.key === "string" &&
      SITE_SETTING_FIELDS[row.key]
    ) {
      return {
        ...permissionField,
        label: SITE_SETTING_LABELS[row.key] ?? "Setting values",
        structuredFields: SITE_SETTING_FIELDS[row.key],
      };
    }
    return permissionField;
  });
  const [initialValues] = useState<FormValues>(
    () =>
      Object.fromEntries(
        configuredFields.map((field) => [
          field.key,
          initialFieldValue(field, row),
        ]),
      ) as FormValues,
  );
  const [values, setValues] = useState<FormValues>(initialValues);
  const [stepIndex, setStepIndex] = useState(0);
  const [farthestStep, setFarthestStep] = useState(0);
  const [draftReady, setDraftReady] = useState(!draftKey);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [resourceVersion, setResourceVersion] = useState<unknown>(row?.version);
  const mutationRow = row
    ? {
        ...row,
        ...(resourceVersion === undefined ? {} : { version: resourceVersion }),
      }
    : undefined;
  const fields = configuredFields.map((field) =>
    field.optionsForValues
      ? { ...field, options: field.optionsForValues(values) }
      : field,
  );
  const [busyFields, setBusyFields] = useState<string[]>([]);
  const fieldByKey = useMemo(
    () => new Map(fields.map((field) => [field.key, field])),
    [fields],
  );
  const wizardSteps = useMemo(() => {
    if (!steps?.length) return [];
    const configuredKeys = new Set(fields.map((field) => field.key));
    return steps
      .map((step) => ({
        ...step,
        fieldKeys: step.fieldKeys.filter((key) => configuredKeys.has(key)),
      }))
      .filter((step) => step.id === "review" || step.fieldKeys.length > 0);
  }, [fields, steps]);
  const activeStep = wizardSteps[stepIndex];
  const reviewStepActive = activeStep?.id === "review";
  const formNoun = config.detail?.noun ?? config.title.replace(/^All\s+/i, "");
  const visibleFields = activeStep
    ? activeStep.fieldKeys.flatMap((key) => {
        const field = fieldByKey.get(key);
        return field ? [field] : [];
      })
    : fields;
  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);

  useEffect(() => {
    if (!draftKey) return;
    const recovered: FormValues = {};
    try {
      const stored = window.sessionStorage.getItem(draftKey);
      if (stored) {
        const parsed = JSON.parse(stored) as Record<string, unknown>;
        const allowed = new Set(recoverableFields);
        for (const [key, value] of Object.entries(parsed)) {
          if (!allowed.has(key)) continue;
          if (
            typeof value === "string" ||
            typeof value === "boolean" ||
            (Array.isArray(value) &&
              value.every((item) => typeof item === "string"))
          ) {
            recovered[key] = value;
          }
        }
      }
    } catch {
      window.sessionStorage.removeItem(draftKey);
    }
    const frame = window.requestAnimationFrame(() => {
      if (Object.keys(recovered).length) {
        setValues((current) => ({ ...current, ...recovered }));
      }
      setDraftReady(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [draftKey, recoverableFields]);

  useEffect(() => {
    if (!draftKey || !draftReady) return;
    const allowed = new Set(recoverableFields);
    const safeDraft = Object.fromEntries(
      Object.entries(values).filter(([key]) => allowed.has(key)),
    );
    if (Object.keys(safeDraft).length) {
      window.sessionStorage.setItem(draftKey, JSON.stringify(safeDraft));
    }
  }, [draftKey, draftReady, recoverableFields, values]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const savedOptionFor = (field: WorkspaceField) => {
    if (!row || !field.selectedLabelFromRow) return undefined;
    const savedValue = row[field.key];
    if (savedValue == null || savedValue === "") return undefined;
    const label = field.selectedLabelFromRow(row);
    return label ? { value: String(savedValue), label } : undefined;
  };

  const updateFieldValue = (field: WorkspaceField, nextValue: FormValue) => {
    setValues((current) => {
      const next = {
        ...current,
        [field.key]: nextValue,
        ...Object.fromEntries(
          (field.clearOnChange ?? []).map((key) => [key, ""]),
        ),
      };
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
      if (mutation.prepare) payload = mutation.prepare(payload, mutationRow);
      return api<unknown>(endpointFor(mutation, mutationRow), {
        method: mutation.method ?? "POST",
        headers:
          mutationRow && mutation.headers
            ? mutation.headers(mutationRow)
            : undefined,
        body: payload,
      });
    },
    onSuccess: async (result) => {
      const savedRow = workspaceRowFromMutationResult(result);
      toast.success(mutation.successMessage);
      if (draftKey) window.sessionStorage.removeItem(draftKey);
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

  function missingRequiredField(checkFields: WorkspaceField[]) {
    return checkFields.find((field) => {
      if (!field.required) return false;
      const value = values[field.key];
      return Array.isArray(value)
        ? value.length === 0
        : value == null || String(value).trim() === "";
    });
  }

  function scrollFormTop() {
    const reduceMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (typeof window.scrollTo === "function") {
      window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    }
  }

  function goNext() {
    const missing = missingRequiredField(visibleFields);
    if (missing) {
      toast.error(`${missing.label} is required`);
      document.getElementById(`workspace-${mode}-${missing.key}`)?.focus();
      return;
    }
    const next = Math.min(wizardSteps.length - 1, stepIndex + 1);
    setStepIndex(next);
    setFarthestStep((current) => Math.max(current, next));
    scrollFormTop();
  }

  function goToStep(index: number) {
    if (index < 0 || index > farthestStep) return;
    setStepIndex(index);
    scrollFormTop();
  }

  function requestClose() {
    if (dirty) {
      setConfirmDiscard(true);
      return;
    }
    close();
  }

  function reviewValue(field: WorkspaceField, value: FormValue) {
    if (field.type === "checkbox") return value ? "Yes" : "No";
    if (field.type === "media" || field.type === "multiselect") {
      const count = Array.isArray(value) ? value.length : value ? 1 : 0;
      return `${count} selected`;
    }
    if (field.type === "richtext") {
      return String(value)
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    }
    if (field.type === "json") {
      try {
        const parsed = JSON.parse(String(value)) as unknown;
        if (Array.isArray(parsed))
          return `${parsed.length} item${parsed.length === 1 ? "" : "s"}`;
        if (parsed && typeof parsed === "object") {
          return `${Object.keys(parsed).length} detail${Object.keys(parsed).length === 1 ? "" : "s"}`;
        }
      } catch {
        return "Needs attention";
      }
    }
    return String(value || "Not provided");
  }

  return (
    <div
      className={variant === "page" ? "mx-auto w-full max-w-5xl" : undefined}
    >
      {variant === "page" ? (
        <Button
          type="button"
          variant="ghost"
          className="mb-4 w-fit px-1 text-xs text-muted hover:bg-transparent hover:text-ink"
          onClick={requestClose}
        >
          <ArrowLeft className="size-4" />
          {mode === "edit"
            ? `Back to ${formNoun.toLowerCase()}`
            : `Back to ${config.title}`}
        </Button>
      ) : null}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow text-coral">
            {mode === "create"
              ? mutation.clientOnly
                ? config.title
                : `New ${formNoun.toLowerCase()}`
              : `Edit ${formNoun.toLowerCase()}`}
          </p>
          <h2 className="mt-1.5 text-xl font-semibold tracking-tight">
            {mutation.label}
          </h2>
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">
            {wizardSteps.length
              ? "Work through each section, then review everything before saving. Required fields are marked."
              : "Required fields are marked. Save when the information is complete."}
          </p>
        </div>
        {showCloseButton ? (
          <Button
            size="icon"
            variant="ghost"
            onClick={requestClose}
            aria-label="Close form"
          >
            <X className="size-5" />
          </Button>
        ) : null}
      </div>
      {wizardSteps.length ? (
        <nav
          aria-label="Form progress"
          className="workspace-stepper scrollbar-subtle mt-5"
        >
          {wizardSteps.map((step, index) => (
            <button
              key={step.id}
              type="button"
              disabled={index > farthestStep}
              aria-current={index === stepIndex ? "step" : undefined}
              data-complete={index <= farthestStep || undefined}
              onClick={() => goToStep(index)}
              className="workspace-step disabled:opacity-45"
            >
              <span className="workspace-step-node" aria-hidden="true">
                {index !== stepIndex && index <= farthestStep ? (
                  <Check className="size-3" />
                ) : (
                  index + 1
                )}
              </span>
              <span className="min-w-0">
                <span
                  className="block text-[.62rem] font-bold tracking-[.12em] text-muted uppercase"
                  aria-hidden="true"
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span
                  className={cn(
                    "mt-1 block truncate text-sm",
                    index === stepIndex
                      ? "font-semibold text-ink"
                      : "font-medium text-muted",
                  )}
                >
                  {step.title}
                </span>
              </span>
            </button>
          ))}
        </nav>
      ) : null}
      <form
        className={`mt-5 grid gap-x-5 gap-y-5 sm:grid-cols-2 ${
          variant === "page"
            ? "workspace-folio rounded-2xl p-4 sm:p-6"
            : ""
        }`}
        onSubmit={(event) => {
          event.preventDefault();
          if (wizardSteps.length && !reviewStepActive) {
            goNext();
            return;
          }
          save.mutate();
        }}
      >
        {activeStep ? (
          <div className="sm:col-span-2">
            <p className="eyebrow text-coral">
              Step {stepIndex + 1} of {wizardSteps.length}
            </p>
            <h3 className="mt-1 text-lg font-semibold tracking-tight">
              {activeStep.title}
            </h3>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
              {activeStep.description}
            </p>
          </div>
        ) : null}
        {reviewStepActive ? (
          <div className="grid gap-0 sm:col-span-2">
            {fields
              .filter((field) => !field.hidden)
              .map((field) => {
                const incomplete = Boolean(missingRequiredField([field]));
                const ownerIndex = wizardStepIndexForField(
                  wizardSteps,
                  field.key,
                );
                return (
                  <button
                    key={field.key}
                    type="button"
                    aria-label={`Edit ${field.label}`}
                    onClick={() =>
                      ownerIndex >= 0 ? goToStep(ownerIndex) : undefined
                    }
                    className={cn(
                      "grid gap-1 border-t border-line/80 py-4 text-left transition first:border-t-0 hover:bg-ink/[.02] sm:grid-cols-[11rem_minmax(0,1fr)_auto] sm:items-start sm:gap-6",
                      incomplete && "bg-coral/[.04]",
                    )}
                  >
                    <p className="text-[.62rem] font-bold tracking-[.1em] text-muted uppercase">
                      {field.label}
                    </p>
                    <p className="line-clamp-4 text-sm leading-6 font-medium text-ink">
                      {reviewValue(field, values[field.key] ?? "") ||
                        "Not provided"}
                    </p>
                    {incomplete ? (
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-coral">
                        <CircleAlert className="size-3.5" />
                        Required
                      </span>
                    ) : (
                      <span className="text-xs font-semibold text-coral">
                        Edit
                      </span>
                    )}
                  </button>
                );
              })}
          </div>
        ) : (
          visibleFields.map((field, index) => {
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
                className={`grid content-start gap-2.5 ${wide ? "sm:col-span-2" : ""}`}
              >
                <label
                  id={labelId}
                  htmlFor={fieldId}
                  className="text-[.68rem] font-bold tracking-[.1em] text-muted uppercase"
                >
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
                    className="workspace-control flex min-h-10 items-center gap-3 rounded-xl px-4"
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
                    autoFocus={variant !== "page" && index === 0}
                    required={field.required}
                    value={String(value)}
                    placeholder={field.placeholder}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [field.key]: event.target.value,
                      }))
                    }
                    className="workspace-control min-h-32 rounded-xl p-4 text-sm font-normal"
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
                  <>
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
                                  next.blocked_download_media_ids =
                                    selected.filter((id) => blocked.has(id));
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
                            autoFocus={variant !== "page" && index === 0}
                            fallbackOption={savedOptionFor(field)}
                            formValues={values}
                            record={mutationRow}
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
                    {config.queryKey === "galleries" &&
                    field.key === "media_asset_ids" ? (
                      <GoogleDriveGalleryImport
                        galleryId={
                          mode === "edit" && row?.id
                            ? String(row.id)
                            : undefined
                        }
                        folderUrlHint={
                          typeof values.external_album_url === "string"
                            ? values.external_album_url
                            : undefined
                        }
                        onImported={(
                          mediaIds,
                          importedFolderUrl,
                          galleryVersion,
                        ) => {
                          if (galleryVersion !== undefined) {
                            setResourceVersion(galleryVersion);
                          }
                          setValues((current) => {
                            const existing = Array.isArray(
                              current.media_asset_ids,
                            )
                              ? current.media_asset_ids.map(String)
                              : [];
                            const merged = [
                              ...existing,
                              ...mediaIds.filter(
                                (id) => !existing.includes(id),
                              ),
                            ];
                            return {
                              ...current,
                              media_asset_ids: merged,
                              external_album_url:
                                current.external_album_url || importedFolderUrl,
                            };
                          });
                        }}
                      />
                    ) : null}
                  </>
                ) : field.type === "select" ? (
                  <WorkspaceSelect
                    id={fieldId}
                    labelledBy={labelId}
                    field={field}
                    value={value}
                    autoFocus={variant !== "page" && index === 0}
                    fallbackOption={savedOptionFor(field)}
                    formValues={values}
                    record={mutationRow}
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
                    autoFocus={variant !== "page" && index === 0}
                    required={field.required}
                    type={
                      field.type === "list" ? "text" : (field.type ?? "text")
                    }
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
                        ? "workspace-control min-h-11 rounded-xl px-4 text-sm font-semibold"
                        : "workspace-control min-h-10 rounded-xl px-4 text-sm font-normal"
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
          })
        )}
        <div
          className={`flex flex-wrap justify-between gap-2 sm:col-span-2 ${
            variant === "page"
              ? "dashboard-action-dock"
              : "mt-4 border-t border-line/80 pt-4"
          }`}
        >
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={requestClose}>
              {cancelLabel}
            </Button>
            {wizardSteps.length && stepIndex > 0 ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => goToStep(stepIndex - 1)}
              >
                <ChevronLeft className="size-4" /> Back
              </Button>
            ) : null}
          </div>
          <Button
            size="sm"
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
            {wizardSteps.length && !reviewStepActive
              ? "Continue"
              : busyFields.length
                ? "Checking upload…"
                : (mutation.submitLabel ??
                  (mode === "create" ? mutation.label : "Save changes"))}
          </Button>
        </div>
      </form>
      <ConfirmDialog
        open={confirmDiscard}
        title="Discard unsaved changes?"
        description="The changes in this form have not been saved. Leaving now will discard this editing session."
        confirmLabel="Discard changes"
        danger
        onCancel={() => setConfirmDiscard(false)}
        onConfirm={() => {
          if (draftKey) window.sessionStorage.removeItem(draftKey);
          setConfirmDiscard(false);
          close();
        }}
      />
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
}: {
  config: WorkspaceConfig;
  headerAction?: React.ReactNode;
  /** Kept for tabbed hubs that previously hid the list title. */
  embedded?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const presentation = workspacePresentationFor(config);
  const [search, setSearch] = useState(() => searchParams.get("q") ?? "");
  const [panel, setPanel] = useState<WorkspacePanel | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<{
    mutation: WorkspaceMutation;
    row: WorkspaceRow;
  }>();
  const [filtersOpen, setFiltersOpen] = useState(() =>
    (config.filters ?? []).some((filter) => searchParams.has(filter.key)),
  );
  const [filters, setFilters] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (config.filters ?? [])
        .map((filter) => [filter.key, searchParams.get(filter.key) ?? ""])
        .filter(([, value]) => Boolean(value)),
    ),
  );
  const [sort, setSort] = useState<
    | {
        key: string;
        direction: "asc" | "desc";
      }
    | undefined
  >(() => {
    const key = searchParams.get("sort_by");
    if (!key) return undefined;
    return {
      key,
      direction: searchParams.get("sort_dir") === "desc" ? "desc" : "asc",
    };
  });
  const [page, setPage] = useState(() => {
    const parsed = Number(searchParams.get("page") ?? "1");
    return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
  });
  const debouncedSearch = useDebouncedValue(search);
  const queryEndpoint = workspaceEndpoint(
    config,
    page,
    debouncedSearch,
    filters,
    sort,
  );

  const selected = panel && panel.view !== "create" ? panel.row : null;

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (debouncedSearch.trim()) params.set("q", debouncedSearch.trim());
    else params.delete("q");
    for (const filter of config.filters ?? []) {
      const value = filters[filter.key];
      if (value) params.set(filter.key, value);
      else params.delete(filter.key);
    }
    if (sort) {
      params.set("sort_by", sort.key);
      params.set("sort_dir", sort.direction);
    } else {
      params.delete("sort_by");
      params.delete("sort_dir");
    }
    if (page > 1) params.set("page", String(page));
    else params.delete("page");
    const query = params.toString();
    const next = query ? `${pathname}?${query}` : pathname;
    const current = searchParams.toString()
      ? `${pathname}?${searchParams.toString()}`
      : pathname;
    if (next !== current) router.replace(next, { scroll: false });
  }, [
    config.filters,
    debouncedSearch,
    filters,
    page,
    pathname,
    router,
    searchParams,
    sort,
  ]);

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
      api(endpointFor(mutation, row), {
        method: mutation.method ?? "POST",
        headers: mutation.headers ? mutation.headers(row) : undefined,
      }),
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
      setPendingConfirmation(undefined);
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
  const visibleColumns = useMemo(
    () =>
      config.columns.filter((column) => {
        if (["slug", "media_name", "rules", "value"].includes(column.key)) {
          return false;
        }
        if (column.key === "version" && config.key !== "documents") {
          return false;
        }
        return true;
      }),
    [config.columns, config.key],
  );
  const cardLayout = ["cards", "media"].includes(
    presentation?.listVariant ?? "",
  );
  const analyticsSnapshot =
    presentation?.listVariant === "analytics"
      ? analyticsSnapshotFrom(query.data)
      : null;
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

  const detailImages = useMemo(
    () => (selected ? recordImages(selected) : []),
    [selected],
  );
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
    if (presentation?.listVariant === "analytics") return;
    const href =
      presentation?.viewHref?.(row) ??
      presentation?.detailHref?.(row) ??
      config.detailHref?.(row);
    if (href) {
      const current = `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
      router.push(`${href}?returnTo=${encodeURIComponent(current)}`);
      return;
    }
    setPanel({ view: "details", row });
  }

  function openEditor(row: WorkspaceRow, mutation: WorkspaceMutation) {
    const href =
      mutation === config.update
        ? (presentation?.editHref?.(row) ?? config.updateHref?.(row))
        : undefined;
    if (href) {
      const current = `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
      router.push(`${href}?returnTo=${encodeURIComponent(current)}`);
      return;
    }
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

  function openCreate() {
    if (!config.create) return;
    if (presentation?.createHref) {
      const current = `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
      router.push(
        `${presentation.createHref}?returnTo=${encodeURIComponent(current)}`,
      );
      return;
    }
    setPanel({ mutation: config.create, view: "create" });
  }

  function runAction(mutation: WorkspaceMutation, row: WorkspaceRow) {
    if (mutation.confirm) {
      setPendingConfirmation({ mutation, row });
      return;
    }
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
  const collection = collectionLabel(config.detail?.noun);
  const hasActiveQuery =
    Boolean(search.trim()) || Object.values(filters).some(Boolean);
  const activeFilterEntries = visibleFilters.flatMap((filter) => {
    const value = filters[filter.key];
    return value ? [{ key: filter.key, label: filter.label, value }] : [];
  });
  const actions = (
    <div className="flex shrink-0 flex-wrap items-center gap-2">
      {headerAction}
      {config.exportUrl && can(config.exportPermission ?? "members.export") ? (
        <Button size="sm" variant="ghost" onClick={exportRecords}>
          <ArrowDownToLine className="size-4" /> Export
        </Button>
      ) : null}
      {config.create && can(config.create.permission) ? (
        <Button size="sm" onClick={openCreate}>
          <CirclePlus className="size-4" /> {config.create.label}
        </Button>
      ) : null}
    </div>
  );

  return (
    <div>
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line/70 px-4 py-3 sm:flex-row sm:items-center sm:px-5">
          {analyticsSnapshot ? (
            <p className="min-w-0 flex-1 text-[13px] text-muted">
              {analyticsSnapshot.generatedAt
                ? `Snapshot as of ${display(analyticsSnapshot.generatedAt, "generated_at")}`
                : "Association snapshot"}
            </p>
          ) : (
            <label className="flex min-h-10 flex-1 items-center gap-3 rounded-full bg-ink/[.035] px-3.5">
              <Search className="size-4 text-muted" />
              <span className="sr-only">Search {collection}</span>
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                placeholder={`Search ${collection}`}
                className="w-full bg-transparent text-sm outline-none"
              />
              {search ? (
                <button
                  type="button"
                  className="grid size-7 place-items-center rounded-full text-muted transition hover:bg-ink/8 hover:text-ink"
                  onClick={() => {
                    setSearch("");
                    setPage(1);
                  }}
                  aria-label="Clear search"
                >
                  <X className="size-3.5" />
                </button>
              ) : null}
            </label>
          )}
          <div className="flex flex-wrap items-center gap-2">
            {visibleFilters.length ? (
              <Button
                size="sm"
                variant={
                  filtersOpen || activeFilterEntries.length ? "outline" : "ghost"
                }
                onClick={() => setFiltersOpen((value) => !value)}
              >
                <Filter className="size-4" /> Filters
                {activeFilterEntries.length ? (
                  <span className="grid size-5 place-items-center rounded-full bg-ink text-[.58rem] text-paper">
                    {activeFilterEntries.length}
                  </span>
                ) : null}
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
            {actions}
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

        {hasActiveQuery ? (
          <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
            <span className="text-[.62rem] font-black tracking-[.08em] text-muted uppercase">
              Showing
            </span>
            {search.trim() ? (
              <button
                type="button"
                className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-line bg-paper px-3 text-[.68rem] font-bold"
                onClick={() => {
                  setSearch("");
                  setPage(1);
                }}
              >
                “{search.trim()}”
                <X className="size-3" />
              </button>
            ) : null}
            {activeFilterEntries.map((filter) => (
              <button
                key={filter.key}
                type="button"
                className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-line bg-paper px-3 text-[.68rem] font-bold"
                onClick={() => {
                  setPage(1);
                  setFilters((current) => ({ ...current, [filter.key]: "" }));
                }}
              >
                {filter.label}: {humanize(filter.value)}
                <X className="size-3" />
              </button>
            ))}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setPage(1);
                setSearch("");
                setFilters({});
              }}
            >
              Clear all
            </Button>
          </div>
        ) : null}

        {query.isLoading ? (
          <div className="grid gap-2 p-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="h-9 animate-pulse rounded-lg bg-ink/5"
              />
            ))}
          </div>
        ) : query.error ? (
          <div className="grid place-items-center px-6 py-12 text-center">
            <span className="grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
              <Inbox className="size-5" />
            </span>
            <p className="mt-4 text-lg font-semibold tracking-tight">
              {config.title} could not be loaded
            </p>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted">
              Check your connection or access, then try again.
            </p>
            <Button size="sm" className="mt-5" onClick={() => query.refetch()}>
              <RefreshCw className="size-4" /> Try again
            </Button>
          </div>
        ) : analyticsSnapshot ? (
          analyticsSnapshot.groups.length ? (
            <AnalyticsDashboard snapshot={analyticsSnapshot} />
          ) : (
            <div className="grid place-items-center px-6 py-12 text-center">
              <span className="grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
                <Inbox className="size-5" />
              </span>
              <p className="mt-4 text-lg font-semibold tracking-tight">
                No analytics snapshot yet
              </p>
              <p className="mt-2 max-w-md text-sm leading-6 text-muted">
                Membership, publishing, and event counts will appear here when
                the association has records to summarize.
              </p>
            </div>
          )
        ) : rows.length === 0 ? (
          <div className="grid place-items-center px-6 py-12 text-center">
            <span className="grid size-12 place-items-center rounded-2xl bg-ink/5 text-muted">
              <ListEmptyGlyph variant={presentation?.listVariant} />
            </span>
            <p className="mt-4 text-lg font-semibold tracking-tight">
              {hasActiveQuery
                ? `No matching ${collection}`
                : `No ${collection} yet`}
            </p>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted">
              {hasActiveQuery
                ? "Try a different search or clear the current filters."
                : config.create && can(config.create.permission)
                  ? `Create the first ${config.detail?.noun.toLowerCase() ?? "item"} to start this workspace.`
                  : "Nothing has been added here yet."}
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {hasActiveQuery ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setPage(1);
                    setSearch("");
                    setFilters({});
                  }}
                >
                  Clear search and filters
                </Button>
              ) : null}
              {config.create && can(config.create.permission) && !hasActiveQuery ? (
                <Button size="sm" onClick={openCreate}>
                  <CirclePlus className="size-4" /> {config.create.label}
                </Button>
              ) : null}
            </div>
          </div>
        ) : presentation?.listVariant === "directory" ? (
          <div className="grid gap-3 p-3 sm:p-4 lg:grid-cols-2">
            {visibleRows.map((row, index) => {
              const rowActions = rowActionsFor(
                row,
                config,
                permissions,
                user.data?.id,
                deliveryOn,
                presentation?.listViewReplacesActionLabel,
              );
              const titleKey = visibleColumns[0]?.key ?? "title";
              const title = displayWithPersonCase(row[titleKey], titleKey, row);
              const metaColumns = visibleColumns.slice(1);
              return (
                <article
                  key={String(row.id ?? row.key ?? index)}
                  className="flex flex-col overflow-hidden rounded-xl border border-line/70 bg-paper"
                >
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center gap-3 px-3 py-3 text-left"
                    onClick={() => openDetails(row)}
                  >
                    <DirectoryAvatar row={row} name={title} />
                    <div className="min-w-0 flex-1">
                      <h3 className="text-sm font-semibold leading-5 break-words">
                        {title}
                      </h3>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {metaColumns.map((column) => {
                          const value = row[column.key];
                          if (value == null || value === "") return null;
                          return (
                            <span
                              key={column.key}
                              className={
                                statusField(column.key)
                                  ? `inline-flex rounded-full px-2 py-0.5 text-[.62rem] font-bold ${statusClass(value)}`
                                  : "workspace-chip"
                              }
                            >
                              {statusField(column.key)
                                ? displayChoice(value, column.key)
                                : displayWithPersonCase(
                                    value,
                                    column.key,
                                    row,
                                  )}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  </button>
                  <div className="border-t border-line/70 px-3 py-2">
                    <WorkspaceRowActions
                      actions={rowActions}
                      pending={action.isPending}
                      onView={() => openDetails(row)}
                      onMutation={(mutation) =>
                        handleRowMutation(row, mutation)
                      }
                      onEdit={() => openEditor(row, rowActions.update!)}
                      onDelete={() => runAction(rowActions.delete!, row)}
                      compact
                    />
                  </div>
                </article>
              );
            })}
          </div>
        ) : presentation?.listVariant === "settings" ? (
          <div className="grid gap-3 p-3 sm:p-4 lg:grid-cols-2">
            {visibleRows.map((row, index) => {
              const rowActions = rowActionsFor(
                row,
                config,
                permissions,
                user.data?.id,
                deliveryOn,
                presentation?.listViewReplacesActionLabel,
              );
              const highlights = settingHighlights(row.value);
              const statusValue = row.enabled ?? row.is_public;
              return (
                <article
                  key={String(row.id ?? row.key ?? index)}
                  className="overflow-hidden rounded-xl border border-line/70 bg-paper"
                >
                  <button
                    type="button"
                    className="block w-full p-4 text-left transition hover:bg-ink/[.02]"
                    onClick={() => openDetails(row)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="eyebrow text-coral">
                          {row.enabled === undefined
                            ? "Portal content"
                            : "Portal capability"}
                        </p>
                        <h3 className="mt-1.5 text-sm font-semibold">
                          <ValueDisplay
                            value={row.key}
                            fieldKey="key"
                            row={row}
                          />
                        </h3>
                      </div>
                      {statusValue !== undefined ? (
                        <span
                          className={`shrink-0 rounded-full px-2.5 py-1 text-[.62rem] font-bold ${statusClass(statusValue)}`}
                        >
                          {row.enabled !== undefined
                            ? row.enabled
                              ? "Enabled"
                              : "Disabled"
                            : row.is_public
                              ? "Public"
                              : "Internal"}
                        </span>
                      ) : null}
                    </div>
                    {typeof row.description === "string" && row.description ? (
                      <p className="mt-3 text-xs leading-5 text-muted">
                        {row.description}
                      </p>
                    ) : null}
                    {highlights.length ? (
                      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                        {highlights.map((item) => (
                          <div key={item.key} className="min-w-0">
                            <dt className="text-[.58rem] font-black tracking-wide text-muted uppercase">
                              {item.label}
                            </dt>
                            <dd className="mt-1 truncate text-xs font-bold">
                              <ValueDisplay
                                value={item.value}
                                fieldKey={item.key}
                                row={row}
                                compact
                              />
                            </dd>
                          </div>
                        ))}
                      </dl>
                    ) : null}
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
                      onDelete={() => runAction(rowActions.delete!, row)}
                      compact
                    />
                  </div>
                </article>
              );
            })}
          </div>
        ) : presentation?.listVariant === "timeline" ? (
          <div className="p-3 sm:p-4">
            <ol className="relative grid gap-3 before:absolute before:top-3 before:bottom-3 before:left-[.43rem] before:w-px before:bg-line">
              {visibleRows.map((row, index) => {
                const rowActions = rowActionsFor(
                  row,
                  config,
                  permissions,
                  user.data?.id,
                  deliveryOn,
                  presentation?.listViewReplacesActionLabel,
                );
                const state = row.outcome ?? row.status;
                const title = row.action ?? row.kind ?? "Activity";
                const context = [row.actor_name, row.resource_type]
                  .filter(Boolean)
                  .map(String)
                  .join(" · ");
                const note = row.reason ?? row.error_message;
                const progress =
                  typeof row.progress === "number" ? row.progress : null;
                return (
                  <li
                    key={String(row.id ?? row.key ?? index)}
                    className="relative grid grid-cols-[.9rem_minmax(0,1fr)] gap-4"
                  >
                    <span className="relative z-10 mt-5 size-3.5 rounded-full border-[3px] border-paper bg-coral shadow-[0_0_0_1px_var(--line)]" />
                    <article className="overflow-hidden rounded-xl border border-line/70 bg-paper">
                      <button
                        type="button"
                        className="block w-full p-4 text-left transition hover:bg-ink/[.02] sm:p-5"
                        onClick={() => openDetails(row)}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h3 className="text-sm font-black">
                              {humanize(String(title))}
                            </h3>
                            {context ? (
                              <p className="mt-1 text-xs text-muted">
                                {context}
                              </p>
                            ) : null}
                          </div>
                          <div className="flex items-center gap-2">
                            {state !== undefined ? (
                              <span
                                className={`rounded-full px-2.5 py-1 text-[.62rem] font-bold ${statusClass(state)}`}
                              >
                                {displayChoice(state, "status")}
                              </span>
                            ) : null}
                            {row.created_at ? (
                              <span className="text-[.62rem] font-bold text-muted">
                                {display(row.created_at, "created_at")}
                              </span>
                            ) : null}
                          </div>
                        </div>
                        {typeof note === "string" && note ? (
                          <p className="mt-3 text-xs leading-5 text-muted">
                            {note}
                          </p>
                        ) : null}
                        {progress !== null ? (
                          <div className="mt-4">
                            <div className="mb-1.5 flex justify-between text-[.6rem] font-bold text-muted">
                              <span>Progress</span>
                              <span>{Math.round(progress)}%</span>
                            </div>
                            <div className="h-1.5 overflow-hidden rounded-full bg-ink/8">
                              <span
                                className="block h-full rounded-full bg-coral"
                                style={{
                                  width: `${Math.min(100, Math.max(0, progress))}%`,
                                }}
                              />
                            </div>
                          </div>
                        ) : null}
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
                          onDelete={() => runAction(rowActions.delete!, row)}
                          compact
                        />
                      </div>
                    </article>
                  </li>
                );
              })}
            </ol>
          </div>
        ) : config.layout === "grid" || cardLayout ? (
          <div className="grid gap-3 p-3 sm:grid-cols-2 sm:p-4 xl:grid-cols-3">
            {visibleRows.map((row, index) => {
              const rowActions = rowActionsFor(
                row,
                config,
                permissions,
                user.data?.id,
                deliveryOn,
                presentation?.listViewReplacesActionLabel,
              );
              const titleKey = visibleColumns[0]?.key ?? "title";
              const metaColumns = visibleColumns.slice(1);
              const albumCard =
                presentation?.listVariant === "media" ||
                config.key === "galleries";
              return (
                <article
                  key={String(row.id ?? row.key ?? index)}
                  className="group overflow-hidden rounded-xl border border-line/70 bg-paper text-left"
                >
                  <button
                    type="button"
                    className="w-full text-left"
                    onClick={() => openDetails(row)}
                  >
                    <RecordCardMedia
                      row={row}
                      aspect={
                        albumCard
                          ? "landscape"
                          : (config.gridAspect ?? "landscape")
                      }
                    />
                    <div className="grid gap-2 p-3">
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold leading-5 break-words">
                          {displayWithPersonCase(row[titleKey], titleKey, row)}
                        </h3>
                        {metaColumns.length ? (
                          <div className="mt-1.5 flex flex-wrap gap-1">
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
                                    : `${column.label}: ${displayWithPersonCase(value, column.key, row)}`;
                              return (
                                <span
                                  key={column.key}
                                  className={
                                    statusField(column.key)
                                      ? `inline-flex rounded-full px-2.5 py-1 text-[.62rem] font-bold ${statusClass(value)}`
                                      : "workspace-chip"
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
                  <div className="border-t border-line/70 px-3 py-2">
                    <WorkspaceRowActions
                      actions={rowActions}
                      pending={action.isPending}
                      onView={() => openDetails(row)}
                      onMutation={(mutation) =>
                        handleRowMutation(row, mutation)
                      }
                      onEdit={() => openEditor(row, rowActions.update!)}
                      onDelete={() => runAction(rowActions.delete!, row)}
                      compact
                    />
                  </div>
                </article>
              );
            })}
          </div>
        ) : visibleColumns.length === 0 ? (
          <div className="grid gap-3 p-3 sm:grid-cols-2 sm:p-4 xl:grid-cols-3">
            {visibleRows.map((row, index) => {
              const rowActions = rowActionsFor(
                row,
                config,
                permissions,
                user.data?.id,
                deliveryOn,
                presentation?.listViewReplacesActionLabel,
              );
              return (
                <div
                  key={String(row.id ?? row.key ?? index)}
                  className="rounded-xl border border-line/70 bg-paper p-4 text-left"
                >
                  <button
                    type="button"
                    className="w-full text-left"
                    onClick={() => openDetails(row)}
                  >
                    <span className="text-[.62rem] font-black tracking-wide text-coral uppercase">
                      {humanize(String(row.group ?? "Metric"))}
                    </span>
                    <b className="mt-1.5 block text-sm font-semibold">
                      {humanize(String(row.key ?? "Value"))}
                    </b>
                    <span className="mt-2 block text-lg font-semibold">
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
                      onDelete={() => runAction(rowActions.delete!, row)}
                      compact
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="scrollbar-subtle overflow-x-auto">
            <table
              className="workspace-data-table w-full min-w-[36rem] border-collapse text-left"
              aria-label={config.title}
            >
              <thead>
                <tr className="border-b border-line/70">
                  {visibleColumns.map((column, columnIndex) => {
                    const sortable =
                      !config.serverPagination ||
                      Boolean(
                        config.serverPagination.sortFields?.includes(
                          column.key,
                        ),
                      );
                    const sorted = sort?.key === column.key;
                    return (
                      <th
                        key={column.key}
                        scope="col"
                        aria-sort={
                          sorted
                            ? sort?.direction === "asc"
                              ? "ascending"
                              : "descending"
                            : undefined
                        }
                        className={cn(
                          "px-3 py-2",
                          columnIndex === 0 && "w-[42%] min-w-[12rem]",
                          column.align === "end" && "text-right",
                          (isDateField(column.key) || column.dateStyle) &&
                            "whitespace-nowrap",
                        )}
                      >
                        {sortable ? (
                          <button
                            className={cn(
                              "group inline-flex items-center gap-1 text-[.6rem] font-semibold tracking-[.08em] text-muted uppercase hover:text-ink",
                              column.align === "end" && "justify-end",
                            )}
                            onClick={() => toggleSort(column.key)}
                          >
                            {column.label}
                            <ArrowUpDown
                              className={cn(
                                "size-3",
                                sorted
                                  ? "text-ink/45"
                                  : "opacity-0 group-hover:opacity-50",
                              )}
                            />
                          </button>
                        ) : (
                          <span className="text-[.6rem] font-semibold tracking-[.08em] text-muted uppercase">
                            {column.label}
                          </span>
                        )}
                      </th>
                    );
                  })}
                  <th
                    scope="col"
                    className="w-px px-2 py-2 text-right text-[.6rem] font-semibold tracking-[.08em] text-muted uppercase"
                  >
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
                    presentation?.listViewReplacesActionLabel,
                  );
                  return (
                    <tr
                      key={String(row.id ?? row.key ?? index)}
                      className="cursor-pointer transition hover:bg-ink/[.025]"
                      onClick={() => openDetails(row)}
                    >
                      {visibleColumns.map((column, columnIndex) => (
                        <td
                          key={column.key}
                          className={cn(
                            "px-3 py-2 text-[13px] leading-snug",
                            columnIndex === 0 && "w-[42%] min-w-[12rem]",
                            column.align === "end" &&
                              "text-right tabular-nums",
                            isDateField(column.key) || column.dateStyle
                              ? "whitespace-nowrap"
                              : columnIndex === 0
                                ? "max-w-md"
                                : "max-w-[14rem]",
                          )}
                        >
                          <WorkspaceTableCell
                            column={column}
                            row={row}
                            isPrimary={columnIndex === 0}
                          />
                        </td>
                      ))}
                      <td className="w-px px-2 py-2 text-right whitespace-nowrap">
                        <WorkspaceRowActions
                          actions={rowActions}
                          pending={action.isPending}
                          onView={() => openDetails(row)}
                          onMutation={(mutation) =>
                            handleRowMutation(row, mutation)
                          }
                          onEdit={() => openEditor(row, rowActions.update!)}
                          onDelete={() => runAction(rowActions.delete!, row)}
                          compact
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {analyticsSnapshot ? null : (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-3 py-2 text-[.65rem] text-muted">
          <span>
            {recordTotal} {recordTotal === 1 ? (config.detail?.noun.toLowerCase() ?? "item") : collection}
            {hasActiveQuery ? " matching current filters" : " on file"}
          </span>
          {pageCount > 0 && recordTotal > 0 ? (
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
        )}
      </Card>

      {panel ? (
        <div
          className="fixed inset-0 z-[90] grid place-items-center bg-ink/20 p-4"
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
                    title={
                      detailTitleKey === "full_name" &&
                      typeof panel.row.full_name === "string"
                        ? formatPersonName(panel.row.full_name)
                        : display(panel.row[detailTitleKey], detailTitleKey)
                    }
                    subtitle={
                      config.detail?.subtitleKeys?.length
                        ? config.detail.subtitleKeys
                            .map((key) => display(panel.row[key], key))
                            .filter((value) => value !== "Not provided")
                            .join(" · ") || undefined
                        : undefined
                    }
                    images={detailImages}
                    heroShape={
                      detailImages[0] &&
                      panel.row.profile_media_id &&
                      detailImages[0].id === String(panel.row.profile_media_id)
                        ? "portrait"
                        : "landscape"
                    }
                    entries={(curatedDetails ?? [])
                      .map(({ field, value }) => ({
                        key: field.key,
                        label: field.label,
                        value:
                          field.key === "academic_rank" &&
                          typeof value === "string"
                            ? formatRankForName(
                                typeof panel.row.full_name === "string"
                                  ? panel.row.full_name
                                  : undefined,
                                value,
                              )
                            : field.key === "title" && typeof value === "string"
                              ? matchCaseStyle(
                                  typeof panel.row.full_name === "string"
                                    ? panel.row.full_name
                                    : [panel.row.other_name, panel.row.surname]
                                        .filter(Boolean)
                                        .join(" "),
                                  value,
                                )
                              : value,
                        richtext: field.format === "richtext",
                        format: field.format,
                      }))
                      .filter((entry) => {
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
                    sections={presentation?.detailSections}
                    primaryActions={selectedActions.primary}
                    secondaryActions={selectedActions.secondary}
                    canUpdate={selectedActions.canUpdate}
                    canDelete={selectedActions.canDelete}
                    updateLabel={selectedActions.update?.label}
                    deleteLabel={selectedActions.delete?.label}
                    actionPending={action.isPending}
                    onClose={closePanel}
                    onPrimaryAction={(item) =>
                      handleRowMutation(panel.row, item)
                    }
                    onEdit={() =>
                      openEditor(panel.row, selectedActions.update!)
                    }
                    onDelete={() =>
                      runAction(selectedActions.delete!, panel.row)
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
                    onBack={() => setPanel({ view: "details", row: panel.row })}
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
      <ConfirmDialog
        open={Boolean(pendingConfirmation)}
        title={pendingConfirmation?.mutation.label ?? "Confirm action"}
        description={
          pendingConfirmation?.mutation.confirm ?? "Confirm this action."
        }
        confirmLabel={pendingConfirmation?.mutation.label}
        danger={pendingConfirmation?.mutation.danger}
        busy={action.isPending}
        onCancel={() => setPendingConfirmation(undefined)}
        onConfirm={() => {
          if (pendingConfirmation) action.mutate(pendingConfirmation);
        }}
      />
    </div>
  );
}
