"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import {
  Bell,
  Check,
  CheckCheck,
  LoaderCircle,
  RefreshCw,
  Search,
  Send,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { RichTextEditor } from "@/components/dashboard/rich-text-editor";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { humanize } from "@/lib/utils";

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
type Member = { id: string; full_name: string; email: string; status: string };
type User = { permissions: string[] };
type Page<T> = { items: T[] };

function SendDirectAlertDialog({ close }: { close: () => void }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const [deepLink, setDeepLink] = useState("");
  const members = useQuery({
    queryKey: ["members", "notification-recipients"],
    queryFn: () =>
      api<Page<Member>>("/api/v1/members?page_size=100&status=active"),
  });
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (members.data?.items ?? []).filter(
      (member) =>
        !needle ||
        member.full_name.toLowerCase().includes(needle) ||
        member.email.toLowerCase().includes(needle),
    );
  }, [members.data?.items, search]);
  const send = useMutation({
    mutationFn: () =>
      api("/api/v1/notifications/send", {
        method: "POST",
        body: {
          user_ids: selected,
          category: "direct",
          priority,
          title,
          body,
          deep_link: deepLink || null,
        },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success(
        `Direct alert sent to ${selected.length} member${selected.length === 1 ? "" : "s"}`,
      );
      close();
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Could not send direct alert",
      ),
  });

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  }

  return (
    <div
      className="fixed inset-0 z-[90] flex justify-end bg-black/40 backdrop-blur-sm"
      onMouseDown={close}
    >
      <section
        className="h-full w-full max-w-2xl overflow-y-auto bg-paper p-6 shadow-2xl sm:p-8"
        role="dialog"
        aria-modal="true"
        aria-label="Send direct alert"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="eyebrow text-coral">Member-specific communication</p>
            <h3 className="display-type mt-3 text-4xl">Send direct alert</h3>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted">
              Use this for a one-off alert to selected members. Publish official
              or role-wide communications from{" "}
              <Link
                className="font-bold text-coral underline"
                href="/dashboard/announcements"
              >
                Announcements
              </Link>
              .
            </p>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={close}
            aria-label="Close"
          >
            <X className="size-5" />
          </Button>
        </div>
        <form
          className="mt-8 grid gap-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (!body.trim()) {
              toast.error("Write an alert message before sending.");
              return;
            }
            send.mutate();
          }}
        >
          <label className="grid gap-2 text-xs font-bold">
            Title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              placeholder="Enter the alert title"
              className="min-h-15 rounded-xl border border-line bg-panel px-5 text-base font-semibold outline-none focus:border-ink/25"
            />
          </label>
          <div className="grid gap-2 text-xs font-bold">
            <label
              id="notification-message-label"
              htmlFor="notification-message"
            >
              Message <span className="text-coral">*</span>
            </label>
            <RichTextEditor
              id="notification-message"
              labelledBy="notification-message-label"
              value={body}
              onChange={setBody}
              required
              placeholder="Write the notification message…"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="grid gap-2 text-xs font-bold">
              Priority
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value)}
                className="min-h-11 rounded-xl border border-line bg-panel px-4 text-sm font-normal outline-none"
              >
                {["low", "normal", "high", "urgent"].map((item) => (
                  <option key={item} value={item}>
                    {humanize(item)}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-2 text-xs font-bold">
              Dashboard link
              <input
                value={deepLink}
                onChange={(event) => setDeepLink(event.target.value)}
                placeholder="/dashboard/events"
                className="min-h-11 rounded-xl border border-line bg-panel px-4 text-sm font-normal outline-none"
              />
            </label>
          </div>

          <section>
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-black">Recipients</h4>
              <button
                type="button"
                className="text-xs font-bold text-coral"
                onClick={() =>
                  setSelected((current) =>
                    visible.every((member) => current.includes(member.id))
                      ? current.filter(
                          (id) => !visible.some((member) => member.id === id),
                        )
                      : [
                          ...new Set([
                            ...current,
                            ...visible.map((member) => member.id),
                          ]),
                        ],
                  )
                }
              >
                Select visible
              </button>
            </div>
            <label className="mt-3 flex min-h-11 items-center gap-3 rounded-xl border border-line bg-panel px-3">
              <Search className="size-4 text-muted" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search active members"
                className="w-full bg-transparent text-sm outline-none"
              />
            </label>
            <div className="mt-3 max-h-64 divide-y divide-line overflow-y-auto rounded-xl border border-line">
              {visible.map((member) => (
                <button
                  key={member.id}
                  type="button"
                  onClick={() => toggle(member.id)}
                  className="flex w-full items-center gap-3 p-3 text-left hover:bg-ink/[.025]"
                >
                  <span className="min-w-0 flex-1">
                    <b className="block truncate text-xs">{member.full_name}</b>
                    <small className="text-[.58rem] text-muted">
                      {member.email}
                    </small>
                  </span>
                  <span
                    className={`grid size-6 place-items-center rounded-full border ${selected.includes(member.id) ? "border-sky bg-sky text-white" : "border-line"}`}
                  >
                    {selected.includes(member.id) ? (
                      <Check className="size-3.5" />
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          </section>
          <div className="flex items-center justify-between border-t border-line pt-5">
            <span className="text-xs text-muted">
              {selected.length} selected
            </span>
            <Button disabled={send.isPending || selected.length === 0}>
              {send.isPending ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
              Send direct alert
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function NotificationsClient() {
  const queryClient = useQueryClient();
  const [sending, setSending] = useState(false);
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
  });
  const query = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => api<Page<Notice>>("/api/v1/notifications?page_size=100"),
  });
  const read = useMutation({
    mutationFn: (id: string) =>
      api(`/api/v1/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const deleteNotification = useMutation({
    mutationFn: (id: string) =>
      api(`/api/v1/notifications/${id}/permanent`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("Notification deleted permanently");
    },
  });
  const readAll = useMutation({
    mutationFn: () => api("/api/v1/notifications/read-all", { method: "POST" }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <div className="grid gap-5">
      <header className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow text-coral">Personal inbox</p>
          <h2 className="display-type mt-3 text-4xl sm:text-5xl">
            Notifications
          </h2>
          <p className="mt-3 text-sm text-muted">
            Your personal inbox for official announcements, direct alerts and
            system activity.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {user.data?.permissions.includes("notifications.manage") ? (
            <Button onClick={() => setSending(true)}>
              <Send className="size-4" /> Send direct alert
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => query.refetch()}>
            <RefreshCw className="size-4" /> Refresh
          </Button>
          <Button
            variant="outline"
            onClick={() => readAll.mutate()}
            disabled={readAll.isPending}
          >
            <CheckCheck className="size-4" /> Mark all read
          </Button>
        </div>
      </header>
      <Card className="overflow-hidden">
        <div className="divide-y divide-line">
          {query.data?.items.map((item) => (
            <article
              key={item.id}
              className={`grid grid-cols-[auto_1fr_auto] gap-4 p-5 transition hover:bg-ink/[.025] ${item.read_at ? "opacity-70" : ""}`}
            >
              <button
                onClick={() => !item.read_at && read.mutate(item.id)}
                className={`grid size-10 place-items-center rounded-xl ${item.read_at ? "bg-ink/5" : "bg-coral/10 text-coral"}`}
                aria-label={
                  item.read_at
                    ? "Notification read"
                    : "Mark notification as read"
                }
              >
                <Bell className="size-4" />
              </button>
              <div>
                <span className="flex items-center gap-2">
                  <b className="text-sm">{item.title}</b>
                  {!item.read_at ? (
                    <span className="size-1.5 rounded-full bg-coral" />
                  ) : null}
                </span>
                <div
                  className="mt-1 text-xs leading-6 text-muted [&_a]:font-bold [&_a]:text-coral [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-gold [&_blockquote]:pl-3 [&_li]:ml-4 [&_li]:list-disc [&_p+p]:mt-2"
                  dangerouslySetInnerHTML={{ __html: item.body }}
                />
                <span className="mt-2 block text-[.58rem] font-bold text-muted">
                  {item.category === "announcement"
                    ? "Official announcement"
                    : item.category === "direct"
                      ? "Direct alert"
                      : humanize(item.category)}{" "}
                  · {humanize(item.priority)}
                </span>
                {item.deep_link?.startsWith("/") ? (
                  <Link
                    className="mt-2 inline-block text-xs font-bold text-coral"
                    href={item.deep_link}
                    onClick={() => !item.read_at && read.mutate(item.id)}
                  >
                    Open related item
                  </Link>
                ) : null}
              </div>
              <div className="flex items-start gap-2">
                <span className="whitespace-nowrap text-[.58rem] text-muted">
                  {formatDistanceToNow(new Date(item.created_at), {
                    addSuffix: true,
                  })}
                </span>
                <button
                  className="p-1 text-muted hover:text-red-600 dark:hover:text-red-300"
                  onClick={() => {
                    if (
                      window.confirm(
                        "Permanently delete this notification? This cannot be undone.",
                      )
                    ) {
                      deleteNotification.mutate(item.id);
                    }
                  }}
                  aria-label="Delete notification"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            </article>
          ))}
        </div>
        {!query.isLoading && query.data?.items.length === 0 ? (
          <div className="p-16 text-center">
            <Bell className="mx-auto size-6 text-muted" />
            <p className="mt-4 font-black">You are all caught up</p>
          </div>
        ) : null}
      </Card>
      {sending ? (
        <SendDirectAlertDialog close={() => setSending(false)} />
      ) : null}
    </div>
  );
}
