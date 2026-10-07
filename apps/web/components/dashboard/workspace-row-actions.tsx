"use client";

import { Eye, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import {
  overflowRowItems,
  type RowActionSet,
} from "@/lib/workspace-row-actions";
import type { WorkspaceMutation } from "@/lib/workspaces";
import { cn } from "@/lib/utils";

type MenuPosition = { top: number; left: number };

function menuPositionFor(
  trigger: HTMLElement,
  menuHeight: number,
): MenuPosition {
  const rect = trigger.getBoundingClientRect();
  const width = 192;
  const gap = 4;
  const viewportPad = 8;
  let top = rect.bottom + gap;
  let left = rect.right - width;

  if (top + menuHeight > window.innerHeight - viewportPad) {
    top = Math.max(viewportPad, rect.top - gap - menuHeight);
  }
  left = Math.min(
    Math.max(viewportPad, left),
    window.innerWidth - width - viewportPad,
  );
  return { top, left };
}

function IconActionButton({
  compact,
  label,
  expanded,
  controls,
  hasPopup = false,
  onClick,
  children,
}: {
  compact: boolean;
  label: string;
  expanded?: boolean;
  controls?: string;
  hasPopup?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const popupProps = hasPopup
    ? {
        "aria-haspopup": "menu" as const,
        "aria-expanded": expanded,
        "aria-controls": controls,
      }
    : {};

  if (compact) {
    return (
      <button
        type="button"
        className="grid size-7 min-h-7 place-items-center rounded-md text-muted hover:bg-ink/5 hover:text-ink"
        aria-label={label}
        title={label}
        onClick={onClick}
        {...popupProps}
      >
        {children}
      </button>
    );
  }

  return (
    <Button
      size="icon"
      variant="ghost"
      className="size-8 min-h-8 text-muted hover:text-ink"
      aria-label={label}
      title={label}
      onClick={onClick}
      {...popupProps}
    >
      {children}
    </Button>
  );
}

function menuItems(menu: HTMLElement | null) {
  return Array.from(
    menu?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ??
      [],
  );
}

export function WorkspaceRowActions({
  actions,
  pending = false,
  onView,
  onMutation,
  onEdit,
  onDelete,
  compact = false,
}: {
  actions: RowActionSet;
  pending?: boolean;
  onView: () => void;
  onMutation: (mutation: WorkspaceMutation) => void;
  onEdit: () => void;
  onDelete: () => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<MenuPosition | null>(null);
  const menuId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const overflow = overflowRowItems(actions);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const estimatedHeight = Math.min(320, 8 + overflow.length * 40);
    setPosition(menuPositionFor(triggerRef.current, estimatedHeight));
  }, [overflow.length]);

  const closeMenu = useCallback((restoreFocus = false) => {
    setOpen(false);
    setPosition(null);
    if (restoreFocus) {
      triggerRef.current?.querySelector("button")?.focus();
    }
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    if (menuRef.current && triggerRef.current) {
      setPosition(
        menuPositionFor(triggerRef.current, menuRef.current.offsetHeight),
      );
      menuItems(menuRef.current)[0]?.focus();
    }
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (
        containerRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      ) {
        return;
      }
      closeMenu();
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeMenu(true);
      }
    }
    function onReposition() {
      updatePosition();
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [closeMenu, open, updatePosition]);

  function onMenuKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const items = menuItems(menuRef.current);
    if (!items.length) return;
    const index = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      items[(index + 1 + items.length) % items.length]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      items[(index - 1 + items.length) % items.length]?.focus();
    } else if (event.key === "Home") {
      event.preventDefault();
      items[0]?.focus();
    } else if (event.key === "End") {
      event.preventDefault();
      items[items.length - 1]?.focus();
    } else if (event.key === "Tab") {
      closeMenu();
    }
  }

  const menu =
    open && position && typeof document !== "undefined"
      ? createPortal(
          <div
            ref={menuRef}
            id={menuId}
            role="menu"
            aria-label="Row actions"
            className="workspace-folio fixed z-[95] min-w-48 overflow-hidden rounded-xl py-1"
            style={{ top: position.top, left: position.left }}
            onClick={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
            onKeyDown={onMenuKeyDown}
          >
            {overflow.map((item) => {
              const danger =
                item.kind === "delete" || item.mutation.danger === true;
              return (
                <button
                  key={`${item.kind}-${item.mutation.label}`}
                  type="button"
                  role="menuitem"
                  className={cn(
                    "flex w-full items-center gap-2 px-3 py-2.5 text-left text-xs font-bold hover:bg-ink/5",
                    danger ? "text-red-700 dark:text-red-300" : "text-ink",
                  )}
                  disabled={pending}
                  onClick={() => {
                    closeMenu();
                    if (item.kind === "update") onEdit();
                    else if (item.kind === "delete") onDelete();
                    else onMutation(item.mutation);
                  }}
                >
                  {item.kind === "update" ? (
                    <Pencil className="size-3.5 shrink-0" aria-hidden="true" />
                  ) : null}
                  {item.kind === "delete" ? (
                    <Trash2 className="size-3.5 shrink-0" aria-hidden="true" />
                  ) : null}
                  {item.mutation.label}
                </button>
              );
            })}
          </div>,
          document.body,
        )
      : null;

  function toggleOverflow() {
    if (open) {
      closeMenu();
      return;
    }
    if (triggerRef.current) {
      setPosition(
        menuPositionFor(
          triggerRef.current,
          Math.min(320, 8 + overflow.length * 40),
        ),
      );
    }
    setOpen(true);
  }

  return (
    <div
      ref={containerRef}
      className="relative flex flex-nowrap items-center justify-end gap-0.5"
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => event.stopPropagation()}
    >
      <IconActionButton compact={compact} label="View" onClick={onView}>
        <Eye className="size-3.5" aria-hidden="true" />
      </IconActionButton>
      {overflow.length ? (
        <>
          <span ref={triggerRef} className="inline-flex">
            <IconActionButton
              compact={compact}
              label="More actions"
              hasPopup
              expanded={open}
              controls={menuId}
              onClick={toggleOverflow}
            >
              <MoreHorizontal className="size-3.5" aria-hidden="true" />
            </IconActionButton>
          </span>
          {menu}
        </>
      ) : null}
    </div>
  );
}
