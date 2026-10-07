"use client";

import { AlertTriangle, LoaderCircle, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";

export type ConfirmDialogState = {
  title: string;
  description: string;
  confirmLabel?: string;
  danger?: boolean;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogState & {
  open: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const frame = window.requestAnimationFrame(() =>
      dialogRef.current?.querySelector<HTMLElement>("button")?.focus(),
    );
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab") return;
      const controls = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      if (!controls.length) return;
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus();
    };
  }, [busy, onCancel, open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[120] grid place-items-center bg-ink/20 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-description"
        className="w-full max-w-md overflow-hidden rounded-[1.6rem] bg-paper shadow-[0_30px_90px_rgba(4,16,31,.32)]"
      >
        <div className="flex items-start gap-4 p-7 sm:p-8">
          <span
            className={`grid size-12 shrink-0 place-items-center rounded-2xl ${
              danger
                ? "bg-red-500/12 text-red-700 dark:text-red-300"
                : "bg-gold/18 text-ink"
            }`}
          >
            <AlertTriangle className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="eyebrow text-gold">Please confirm</p>
            <h2
              id="confirm-dialog-title"
              className="display-type mt-2 text-2xl leading-tight"
            >
              {title}
            </h2>
            <p
              id="confirm-dialog-description"
              className="mt-3 text-sm leading-6 text-muted"
            >
              {description}
            </p>
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="-mr-2 -mt-1 text-muted"
            disabled={busy}
            onClick={onCancel}
            aria-label="Close confirmation"
          >
            <X className="size-4" />
          </Button>
        </div>
        <div className="flex justify-end gap-2 px-7 pt-0 pb-6 sm:px-8 sm:pb-7">
          <Button
            type="button"
            variant="ghost"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={busy}
            className={
              danger ? "bg-red-700 text-white hover:bg-red-800" : undefined
            }
            onClick={onConfirm}
          >
            {busy ? <LoaderCircle className="size-4 animate-spin" /> : null}
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
