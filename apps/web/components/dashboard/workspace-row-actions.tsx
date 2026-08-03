"use client";

import { Eye, MoreHorizontal, Pencil, Archive } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import {
  inlineRowMutations,
  overflowRowItems,
  type RowActionSet,
} from "@/lib/workspace-row-actions";
import type { WorkspaceMutation } from "@/lib/workspaces";
import { cn } from "@/lib/utils";

type MenuPosition = { top: number; left: number };

function menuPositionFor(trigger: HTMLElement, menuHeight: number): MenuPosition {
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

export function WorkspaceRowActions({
  actions,
  pending = false,
  onView,
  onMutation,
  onEdit,
  onArchive,
  compact = false,
}: {
  actions: RowActionSet;
  pending?: boolean;
  onView: () => void;
  onMutation: (mutation: WorkspaceMutation) => void;
  onEdit: () => void;
  onArchive: () => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<MenuPosition | null>(null);
  const menuId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const inline = inlineRowMutations(actions);
  const overflow = overflowRowItems(actions);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const estimatedHeight = Math.min(
      320,
      8 + overflow.length * 40,
    );
    setPosition(menuPositionFor(triggerRef.current, estimatedHeight));
  }, [overflow.length]);

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return;
    }
    updatePosition();
    if (menuRef.current && triggerRef.current) {
      setPosition(
        menuPositionFor(triggerRef.current, menuRef.current.offsetHeight),
      );
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
      setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
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
  }, [open, updatePosition]);

  const menu =
    open && position && typeof document !== "undefined"
      ? createPortal(
          <div
            ref={menuRef}
            id={menuId}
            role="menu"
            className="fixed z-[95] min-w-48 overflow-hidden rounded-xl border border-line bg-paper py-1 shadow-xl"
            style={{ top: position.top, left: position.left }}
            onClick={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
          >
            {overflow.map((item) => {
              const danger =
                item.kind === "archive" || item.mutation.danger === true;
              return (
                <button
                  key={`${item.kind}-${item.mutation.label}`}
                  type="button"
                  role="menuitem"
                  className={cn(
                    "flex w-full items-center gap-2 px-3 py-2.5 text-left text-xs font-bold hover:bg-ink/5",
                    danger ? "text-red-700" : "text-ink",
                  )}
                  disabled={pending}
                  onClick={() => {
                    setOpen(false);
                    if (item.kind === "update") onEdit();
                    else if (item.kind === "archive") onArchive();
                    else onMutation(item.mutation);
                  }}
                >
                  {item.kind === "update" ? (
                    <Pencil className="size-3.5 shrink-0" />
                  ) : null}
                  {item.kind === "archive" ? (
                    <Archive className="size-3.5 shrink-0" />
                  ) : null}
                  {item.mutation.label}
                </button>
              );
            })}
          </div>,
          document.body,
        )
      : null;

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative flex flex-wrap items-center gap-1.5",
        compact ? "justify-end" : "justify-end",
      )}
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => event.stopPropagation()}
    >
      <Button
        size="sm"
        variant="outline"
        className="h-8 min-h-8 px-3"
        onClick={onView}
      >
        <Eye className="size-3.5" />
        View
      </Button>
      {inline.map((mutation) => (
        <Button
          key={mutation.label}
          size="sm"
          variant={mutation.openMode === "panel" ? "primary" : "outline"}
          className={cn(
            "h-8 min-h-8 px-3",
            mutation.danger
              ? "border-red-500/30 text-red-700 hover:bg-red-500/10"
              : undefined,
          )}
          disabled={pending}
          onClick={() => onMutation(mutation)}
        >
          {mutation.label}
        </Button>
      ))}
      {overflow.length ? (
        <>
          <span ref={triggerRef} className="inline-flex">
            <Button
              size="icon"
              variant="ghost"
              className="size-8 min-h-8"
              aria-label="More actions"
              aria-expanded={open}
              aria-controls={menuId}
              onClick={() => {
                if (open) {
                  setOpen(false);
                  setPosition(null);
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
              }}
            >
              <MoreHorizontal className="size-4" />
            </Button>
          </span>
          {menu}
        </>
      ) : null}
    </div>
  );
}
