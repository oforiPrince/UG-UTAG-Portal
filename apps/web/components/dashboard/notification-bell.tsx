"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn, humanize } from "@/lib/utils";

type Notice = {
  id: string;
  category: string;
  priority: string;
  title: string;
  body: string;
  deep_link: string | null;
  read_at: string | null;
  created_at: string;
};

type Page<T> = { items: T[] };

function categoryLabel(category: string) {
  if (category === "announcement") return "Official announcement";
  if (category === "direct") return "Direct alert";
  return humanize(category);
}

export function NotificationBell({ enabled }: { enabled: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const unread = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () =>
      api<{ unread: number }>("/api/v1/notifications/unread-count"),
    enabled,
  });
  const recent = useQuery({
    queryKey: ["notifications", "recent-unread"],
    queryFn: () =>
      api<Page<Notice>>("/api/v1/notifications?unread_only=true&page_size=5"),
    enabled: enabled && open,
  });
  const markRead = useMutation({
    mutationFn: (id: string) =>
      api(`/api/v1/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const unreadCount = unread.data?.unread ?? 0;
  const items = recent.data?.items ?? [];

  return (
    <div ref={containerRef} className="relative">
      <Button
        size="icon"
        variant="ghost"
        aria-label="Notifications"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={panelId}
        className="relative"
        onClick={() => setOpen((current) => !current)}
      >
        <Bell className="size-4" />
        {unreadCount > 0 ? (
          <span className="absolute top-1.5 right-1.5 grid size-4 place-items-center rounded-full bg-coral text-[.5rem] font-black text-white">
            {Math.min(unreadCount, 9)}
          </span>
        ) : null}
      </Button>
      {open ? (
        <div
          id={panelId}
          role="dialog"
          aria-label="Recent unread notifications"
          className="absolute top-[calc(100%+0.55rem)] right-0 z-50 w-[min(22rem,calc(100vw-1.5rem))] overflow-hidden rounded-[1.25rem] border border-line bg-paper shadow-[0_18px_60px_rgba(12,25,48,.16)]"
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div>
              <p className="text-[.58rem] font-black tracking-[.14em] text-muted uppercase">
                Inbox
              </p>
              <h2 className="mt-1 text-sm font-black">Unread notifications</h2>
            </div>
            {unreadCount > 0 ? (
              <span className="rounded-full bg-coral/10 px-2.5 py-1 text-[.58rem] font-black text-coral">
                {unreadCount}
              </span>
            ) : null}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {recent.isLoading ? (
              <p className="px-4 py-10 text-center text-xs text-muted">
                Loading unread updates…
              </p>
            ) : items.length ? (
              <ul className="divide-y divide-line">
                {items.map((item) => {
                  const href =
                    item.deep_link?.startsWith("/") === true
                      ? item.deep_link
                      : "/dashboard/notifications";
                  return (
                    <li key={item.id}>
                      <Link
                        href={href}
                        onClick={() => {
                          markRead.mutate(item.id);
                          setOpen(false);
                        }}
                        className="flex items-start gap-3 px-4 py-3.5 transition hover:bg-ink/[.03]"
                      >
                        <span className="mt-1.5 size-2 shrink-0 rounded-full bg-coral" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-xs font-bold text-ink">
                            {item.title}
                          </span>
                          <span className="mt-1 block text-[.58rem] font-bold text-muted">
                            {categoryLabel(item.category)} ·{" "}
                            {formatDistanceToNow(new Date(item.created_at), {
                              addSuffix: true,
                            })}
                          </span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="grid justify-items-center gap-2 px-4 py-10 text-center">
                <Bell className={cn("size-5 text-muted")} />
                <p className="text-xs font-bold">You are all caught up</p>
                <p className="text-[.62rem] text-muted">
                  New association updates will appear here.
                </p>
              </div>
            )}
          </div>
          <div className="border-t border-line bg-panel/55 px-4 py-3">
            <Link
              href="/dashboard/notifications"
              onClick={() => setOpen(false)}
              className="flex min-h-10 items-center justify-center rounded-xl border border-line bg-paper text-xs font-black text-coral transition hover:border-coral/30 hover:bg-coral/5"
            >
              View all notifications
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
