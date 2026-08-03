"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";
import {
  Check,
  CheckCheck,
  Copy,
  FileText,
  Image as ImageIcon,
  Link2,
  LoaderCircle,
  MessageSquarePlus,
  Paperclip,
  Search,
  Send,
  Settings2,
  Trash2,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { initials, formatPersonName, formatRankForName } from "@/lib/utils";

type Conversation = {
  id: string;
  title: string | null;
  kind: "direct" | "group";
  created_by_id: string | null;
  member_count: number;
  unread_count: number;
  last_message_at: string | null;
};
type Message = {
  id: string;
  sender_id: string;
  sender_name: string;
  text: string;
  created_at: string;
  client_message_id: string;
  read_by: number;
  attachments: {
    id: string;
    filename: string;
    content_type: string | null;
    byte_size: number;
    content_url: string;
    thumbnail_url: string | null;
  }[];
};
type DirectoryMember = {
  id: string;
  full_name: string;
  email: string;
  academic_rank: string | null;
};
type GroupMember = {
  user_id: string;
  full_name: string;
  email: string;
  role: "owner" | "admin" | "member";
};
type User = { id: string; full_name: string };
type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};
type ChatUpload = {
  id: string;
  original_filename: string;
  status: "quarantined" | "scanning" | "ready" | "rejected";
};
type PendingFilePreview = {
  name: string;
  url: string;
};
type Invite = {
  id: string;
  join_url: string;
  conversation_title: string;
  expires_at: string;
};

function NewConversationDialog({ close }: { close: () => void }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<"direct" | "group">("direct");
  const [title, setTitle] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const directory = useQuery({
    queryKey: ["chat", "directory", query],
    queryFn: () =>
      api<DirectoryMember[]>(
        `/api/v1/chat/directory?q=${encodeURIComponent(query)}`,
      ),
  });
  const create = useMutation({
    mutationFn: () =>
      api<Conversation>("/api/v1/chat/conversations", {
        method: "POST",
        body: {
          kind,
          title: kind === "group" ? title : null,
          member_ids: selected,
        },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["chat", "conversations"],
      });
      toast.success(
        kind === "group" ? "Group created" : "Conversation started",
      );
      close();
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Could not start chat",
      ),
  });

  function toggle(id: string) {
    setSelected((current) => {
      if (kind === "direct") return current.includes(id) ? [] : [id];
      return current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id];
    });
  }

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-black/40 p-4 backdrop-blur-sm"
      onMouseDown={close}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Start a conversation"
        className="w-full max-w-2xl overflow-hidden rounded-3xl border border-line bg-paper shadow-2xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-line p-6">
          <div>
            <p className="eyebrow text-coral">Member communications</p>
            <h3 className="display-type mt-3 text-3xl">Start a conversation</h3>
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
        <div className="grid gap-5 p-6">
          <div className="grid grid-cols-2 rounded-xl bg-ink/5 p-1">
            {(["direct", "group"] as const).map((option) => (
              <button
                key={option}
                onClick={() => {
                  setKind(option);
                  setSelected([]);
                }}
                className={`min-h-10 rounded-lg text-xs font-bold ${kind === option ? "bg-panel shadow-sm" : "text-muted"}`}
              >
                {option === "direct" ? "Direct chat" : "Member group"}
              </button>
            ))}
          </div>
          {kind === "group" ? (
            <label className="grid gap-2 text-xs font-bold">
              Group name
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="min-h-11 rounded-xl border border-line bg-panel px-4 outline-none focus:border-ink/25"
                required
              />
            </label>
          ) : null}
          <label className="flex min-h-11 items-center gap-3 rounded-xl border border-line bg-panel px-3">
            <Search className="size-4 text-muted" />
            <span className="sr-only">Search members</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search the member directory"
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          <div className="scrollbar-subtle max-h-72 divide-y divide-line overflow-y-auto rounded-xl border border-line">
            {directory.isLoading ? (
              <LoaderCircle className="mx-auto my-12 size-5 animate-spin text-muted" />
            ) : directory.data?.length ? (
              directory.data.map((member) => {
                const checked = selected.includes(member.id);
                return (
                  <button
                    key={member.id}
                    type="button"
                    onClick={() => toggle(member.id)}
                    className="flex w-full items-center gap-3 p-3 text-left hover:bg-ink/[.025]"
                  >
                    <span className="grid size-9 place-items-center rounded-full bg-ink text-[.58rem] font-black text-paper">
                      {initials(member.full_name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <b className="block truncate text-xs">
                        {formatPersonName(member.full_name)}
                      </b>
                      <small className="block truncate text-[.58rem] text-muted">
                        {member.academic_rank
                          ? formatRankForName(
                              member.full_name,
                              member.academic_rank,
                            )
                          : member.email}
                      </small>
                    </span>
                    <span
                      className={`grid size-6 place-items-center rounded-full border ${checked ? "border-sky bg-sky text-white" : "border-line"}`}
                    >
                      {checked ? <Check className="size-3.5" /> : null}
                    </span>
                  </button>
                );
              })
            ) : (
              <p className="p-10 text-center text-xs text-muted">
                No members found.
              </p>
            )}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted">
              {selected.length} selected
            </span>
            <Button
              disabled={
                create.isPending ||
                selected.length < 1 ||
                (kind === "group" && title.trim().length < 2)
              }
              onClick={() => create.mutate()}
            >
              {create.isPending ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <MessageSquarePlus className="size-4" />
              )}
              Start chat
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

function GroupPanel({
  conversation,
  meId,
  close,
}: {
  conversation: Conversation;
  meId: string;
  close: () => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(conversation.title ?? "");
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [inviteUrl, setInviteUrl] = useState("");
  const members = useQuery({
    queryKey: ["chat", "members", conversation.id],
    queryFn: () =>
      api<GroupMember[]>(
        `/api/v1/chat/conversations/${conversation.id}/members`,
      ),
  });
  const directory = useQuery({
    queryKey: ["chat", "directory", directoryQuery],
    queryFn: () =>
      api<DirectoryMember[]>(
        `/api/v1/chat/directory?q=${encodeURIComponent(directoryQuery)}`,
      ),
  });
  const me = members.data?.find((member) => member.user_id === meId);
  const canManage = me?.role === "owner" || me?.role === "admin";

  const mutate = useMutation({
    mutationFn: ({
      endpoint,
      method,
      body,
    }: {
      endpoint: string;
      method: string;
      body?: object;
    }) => api(endpoint, { method, body }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["chat", "members", conversation.id],
        }),
        queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }),
      ]);
      setSelected([]);
      toast.success("Group updated");
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Could not update group",
      ),
  });
  const createInvite = useMutation({
    mutationFn: () =>
      api<Invite>(`/api/v1/chat/conversations/${conversation.id}/invites`, {
        method: "POST",
        body: { expires_in_hours: 72, max_uses: null },
      }),
    onSuccess: async (invite) => {
      const absoluteUrl = `${window.location.origin}${invite.join_url}`;
      setInviteUrl(absoluteUrl);
      await navigator.clipboard.writeText(absoluteUrl).catch(() => undefined);
      toast.success("Invitation link created and copied");
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Could not create invitation",
      ),
  });

  const existingIds = new Set(
    members.data?.map((member) => member.user_id) ?? [],
  );
  const available =
    directory.data?.filter((member) => !existingIds.has(member.id)) ?? [];

  return (
    <div
      className="fixed inset-0 z-[90] flex justify-end bg-black/40 backdrop-blur-sm"
      onMouseDown={close}
    >
      <aside
        className="h-full w-full max-w-xl overflow-y-auto bg-paper p-6 shadow-2xl sm:p-8"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Manage group"
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="eyebrow text-coral">Group controls</p>
            <h3 className="display-type mt-3 text-3xl">
              {conversation.title || "Member group"}
            </h3>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={close}
            aria-label="Close group controls"
          >
            <X className="size-5" />
          </Button>
        </div>

        {canManage ? (
          <div className="mt-7 flex gap-2">
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="min-h-11 flex-1 rounded-xl border border-line bg-panel px-4 text-sm outline-none"
            />
            <Button
              variant="outline"
              disabled={mutate.isPending || title.trim().length < 2}
              onClick={() =>
                mutate.mutate({
                  endpoint: `/api/v1/chat/conversations/${conversation.id}`,
                  method: "PATCH",
                  body: { title },
                })
              }
            >
              Save name
            </Button>
          </div>
        ) : null}

        <section className="mt-8">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-black">Members</h4>
            <span className="text-xs text-muted">
              {members.data?.length ?? 0}
            </span>
          </div>
          <div className="mt-3 divide-y divide-line rounded-xl border border-line">
            {members.data?.map((member) => (
              <div key={member.user_id} className="flex items-center gap-3 p-3">
                <span className="grid size-9 place-items-center rounded-full bg-ink text-[.58rem] font-black text-paper">
                  {initials(member.full_name)}
                </span>
                <span className="min-w-0 flex-1">
                  <b className="block truncate text-xs">{member.full_name}</b>
                  <small className="text-[.58rem] text-muted">
                    {member.role}
                  </small>
                </span>
                {me?.role === "owner" && member.role !== "owner" ? (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        mutate.mutate({
                          endpoint: `/api/v1/chat/conversations/${conversation.id}/members/${member.user_id}/role`,
                          method: "PATCH",
                          body: {
                            role: member.role === "admin" ? "member" : "admin",
                          },
                        })
                      }
                    >
                      {member.role === "admin" ? "Remove admin" : "Make admin"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        if (
                          !window.confirm(
                            `Transfer group ownership to ${member.full_name}? You will remain an administrator.`,
                          )
                        )
                          return;
                        mutate.mutate({
                          endpoint: `/api/v1/chat/conversations/${conversation.id}/owner`,
                          method: "PATCH",
                          body: { user_id: member.user_id },
                        });
                      }}
                    >
                      Make owner
                    </Button>
                  </>
                ) : null}
                {canManage && member.role !== "owner" ? (
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Remove ${member.full_name}`}
                    onClick={() => {
                      if (
                        !window.confirm(
                          `Remove ${member.full_name} from this group?`,
                        )
                      )
                        return;
                      mutate.mutate({
                        endpoint: `/api/v1/chat/conversations/${conversation.id}/members/${member.user_id}`,
                        method: "DELETE",
                      });
                    }}
                  >
                    <X className="size-4" />
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        </section>

        {canManage ? (
          <>
            <section className="mt-8 border-t border-line pt-7">
              <h4 className="text-sm font-black">Invitation link</h4>
              <p className="mt-2 text-xs leading-5 text-muted">
                Create a secure link that expires after 72 hours. Anyone using
                it must sign in as an active member before joining.
              </p>
              {inviteUrl ? (
                <div className="mt-3 flex gap-2">
                  <input
                    readOnly
                    value={inviteUrl}
                    className="min-h-11 min-w-0 flex-1 rounded-xl border border-line bg-panel px-3 text-xs"
                  />
                  <Button
                    size="icon"
                    variant="outline"
                    aria-label="Copy invitation link"
                    onClick={async () => {
                      await navigator.clipboard.writeText(inviteUrl);
                      toast.success("Invitation link copied");
                    }}
                  >
                    <Copy className="size-4" />
                  </Button>
                </div>
              ) : null}
              <Button
                className="mt-3"
                variant="outline"
                disabled={createInvite.isPending}
                onClick={() => createInvite.mutate()}
              >
                {createInvite.isPending ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Link2 className="size-4" />
                )}
                Create invitation link
              </Button>
            </section>
            <section className="mt-8 border-t border-line pt-7">
              <h4 className="text-sm font-black">Add members</h4>
              <label className="mt-3 flex min-h-11 items-center gap-3 rounded-xl border border-line bg-panel px-3">
                <Search className="size-4 text-muted" />
                <input
                  value={directoryQuery}
                  onChange={(event) => setDirectoryQuery(event.target.value)}
                  placeholder="Search members"
                  className="w-full bg-transparent text-sm outline-none"
                />
              </label>
              <div className="mt-3 max-h-56 divide-y divide-line overflow-y-auto rounded-xl border border-line">
                {available.map((member) => (
                  <button
                    key={member.id}
                    onClick={() =>
                      setSelected((current) =>
                        current.includes(member.id)
                          ? current.filter((item) => item !== member.id)
                          : [...current, member.id],
                      )
                    }
                    className="flex w-full items-center gap-3 p-3 text-left hover:bg-ink/[.025]"
                  >
                    <span className="flex-1 text-xs font-bold">
                      {member.full_name}
                    </span>
                    {selected.includes(member.id) ? (
                      <Check className="size-4 text-sky" />
                    ) : null}
                  </button>
                ))}
              </div>
              <Button
                className="mt-3"
                disabled={!selected.length || mutate.isPending}
                onClick={() =>
                  mutate.mutate({
                    endpoint: `/api/v1/chat/conversations/${conversation.id}/members`,
                    method: "POST",
                    body: { member_ids: selected },
                  })
                }
              >
                <UserPlus className="size-4" /> Add selected
              </Button>
            </section>
          </>
        ) : me?.role !== "owner" ? (
          <Button
            className="mt-8"
            variant="outline"
            onClick={() => {
              if (!window.confirm("Leave this group?")) return;
              mutate.mutate({
                endpoint: `/api/v1/chat/conversations/${conversation.id}/members/${meId}`,
                method: "DELETE",
              });
            }}
          >
            Leave group
          </Button>
        ) : null}
      </aside>
    </div>
  );
}

export function ChatClient({ initialInvite = "" }: { initialInvite?: string }) {
  const queryClient = useQueryClient();
  const [active, setActive] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [managing, setManaging] = useState(false);
  const [pendingAttachment, setPendingAttachment] = useState<ChatUpload | null>(
    null,
  );
  const [pendingFilePreview, setPendingFilePreview] =
    useState<PendingFilePreview | null>(null);
  const [inviteToken, setInviteToken] = useState(initialInvite);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
  });
  const conversations = useQuery({
    queryKey: ["chat", "conversations"],
    queryFn: () => api<Conversation[]>("/api/v1/chat/conversations"),
  });
  const filteredConversations = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return conversations.data ?? [];
    return (conversations.data ?? []).filter((item) =>
      (
        item.title ??
        (item.kind === "group" ? "Member group" : "Direct conversation")
      )
        .toLowerCase()
        .includes(needle),
    );
  }, [conversations.data, search]);
  const activeConversationId = active ?? conversations.data?.[0]?.id ?? null;
  const messages = useInfiniteQuery({
    queryKey: ["chat", "messages", activeConversationId],
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "50" });
      if (pageParam) params.set("before", pageParam);
      return api<Page<Message>>(
        `/api/v1/chat/conversations/${activeConversationId}/messages?${params}`,
      );
    },
    enabled: Boolean(activeConversationId),
    initialPageParam: "",
    getNextPageParam: (lastPage) =>
      lastPage.items.length === lastPage.page_size
        ? lastPage.items[0]?.created_at
        : undefined,
  });
  const messageItems = useMemo(
    () =>
      [...(messages.data?.pages ?? [])].reverse().flatMap((page) => page.items),
    [messages.data?.pages],
  );
  const latestMessageId = messageItems.at(-1)?.id;
  const selected = conversations.data?.find(
    (item) => item.id === activeConversationId,
  );
  const inviteDetails = useQuery({
    queryKey: ["chat", "invite", inviteToken],
    queryFn: () =>
      api<{ conversation_title: string; expires_at: string }>(
        `/api/v1/chat/invites/${encodeURIComponent(inviteToken)}`,
      ),
    enabled: Boolean(inviteToken),
    retry: false,
  });
  const attachmentStatus = useQuery({
    queryKey: ["chat", "attachment-upload", pendingAttachment?.id],
    queryFn: () =>
      api<ChatUpload>(
        `/api/v1/chat/attachments/uploads/${pendingAttachment!.id}`,
      ),
    enabled: Boolean(pendingAttachment?.id),
    refetchInterval: (query) =>
      ["quarantined", "scanning"].includes(
        (query.state.data as ChatUpload | undefined)?.status ??
          pendingAttachment?.status ??
          "",
      )
        ? 1500
        : false,
  });
  const attachment = attachmentStatus.data ?? pendingAttachment;

  useEffect(
    () => () => {
      if (pendingFilePreview?.url) {
        URL.revokeObjectURL(pendingFilePreview.url);
      }
    },
    [pendingFilePreview?.url],
  );

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversationId, latestMessageId]);

  useEffect(() => {
    if (!activeConversationId || !messages.data?.pages.length) return;
    api(`/api/v1/chat/conversations/${activeConversationId}/read`, {
      method: "POST",
    })
      .then(() =>
        queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }),
      )
      .catch(() => undefined);
  }, [activeConversationId, messages.data?.pages.length, queryClient]);

  useEffect(() => {
    if (attachmentStatus.data?.status === "rejected") {
      toast.error("The attachment did not pass security scanning");
    }
  }, [attachmentStatus.data?.status]);

  const uploadAttachment = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return api<ChatUpload>("/api/v1/chat/attachments", {
        method: "POST",
        body,
      });
    },
    onSuccess: (upload) => {
      setPendingAttachment(upload);
      toast.success("Attachment uploaded; security scanning has started");
    },
    onError: (error) => {
      setPendingFilePreview(null);
      toast.error(
        error instanceof Error ? error.message : "Attachment could not upload",
      );
    },
  });

  const acceptInvite = useMutation({
    mutationFn: () =>
      api<Conversation>(
        `/api/v1/chat/invites/${encodeURIComponent(inviteToken)}/accept`,
        { method: "POST" },
      ),
    onSuccess: async (conversation) => {
      await queryClient.invalidateQueries({
        queryKey: ["chat", "conversations"],
      });
      setActive(conversation.id);
      setInviteToken("");
      window.history.replaceState({}, "", "/dashboard/chat");
      toast.success("You joined the group");
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Could not join this group",
      ),
  });

  const send = useMutation({
    mutationFn: () =>
      api<Message>(
        `/api/v1/chat/conversations/${activeConversationId}/messages`,
        {
          method: "POST",
          body: {
            text,
            client_message_id: crypto.randomUUID(),
            attachment_media_ids:
              attachment?.status === "ready" ? [attachment.id] : [],
          },
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["chat", "messages", activeConversationId],
      });
      setText("");
      setPendingAttachment(null);
      setPendingFilePreview(null);
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Message could not be sent",
      ),
  });

  const removeMessage = useMutation({
    mutationFn: (messageId: string) =>
      api(`/api/v1/chat/messages/${messageId}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["chat", "messages", activeConversationId],
      });
      toast.success("Message deleted");
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Could not delete message",
      ),
  });

  return (
    <div className="grid gap-5">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow text-coral">Private communications</p>
          <h2 className="display-type mt-3 text-4xl sm:text-5xl">
            Member chat
          </h2>
          <p className="mt-3 text-sm text-muted">
            Direct and group conversations, delivered live.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <MessageSquarePlus className="size-4" /> New conversation
        </Button>
      </header>

      {inviteToken ? (
        <div className="flex flex-col justify-between gap-4 rounded-2xl border border-coral/20 bg-coral/5 p-5 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs font-black text-coral">Group invitation</p>
            <p className="mt-1 text-sm">
              {inviteDetails.isLoading
                ? "Checking this invitation…"
                : inviteDetails.data
                  ? `Join ${inviteDetails.data.conversation_title}?`
                  : "This invitation is unavailable or has expired."}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                setInviteToken("");
                window.history.replaceState({}, "", "/dashboard/chat");
              }}
            >
              Dismiss
            </Button>
            {inviteDetails.data ? (
              <Button
                disabled={acceptInvite.isPending}
                onClick={() => acceptInvite.mutate()}
              >
                {acceptInvite.isPending ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <UserPlus className="size-4" />
                )}
                Join group
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      <Card className="grid min-h-[38rem] overflow-hidden lg:grid-cols-[20rem_1fr]">
        <aside
          className={`${active ? "hidden lg:block" : "block"} border-r border-line`}
        >
          <div className="flex items-center gap-2 border-b border-line p-3">
            <label className="flex min-h-10 flex-1 items-center gap-2 rounded-xl bg-ink/5 px-3">
              <Search className="size-4 text-muted" />
              <span className="sr-only">Find a conversation</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full bg-transparent text-xs outline-none"
                placeholder="Find a conversation"
              />
            </label>
            <Button
              size="icon"
              variant="ghost"
              aria-label="New conversation"
              onClick={() => setCreating(true)}
            >
              <MessageSquarePlus className="size-4" />
            </Button>
          </div>
          <div className="divide-y divide-line">
            {filteredConversations.map((item) => (
              <button
                key={item.id}
                onClick={() => setActive(item.id)}
                className={`flex w-full items-center gap-3 p-4 text-left hover:bg-ink/[.025] ${activeConversationId === item.id ? "bg-ink/[.04]" : ""}`}
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-ink text-[.62rem] font-black text-paper">
                  {initials(
                    item.title ??
                      (item.kind === "group" ? "Group" : "Direct chat"),
                  )}
                </span>
                <span className="min-w-0 flex-1">
                  <b className="block truncate text-xs">
                    {item.title ??
                      (item.kind === "group"
                        ? "Member group"
                        : "Direct conversation")}
                  </b>
                  <small className="mt-1 block truncate text-[.6rem] text-muted">
                    {item.last_message_at
                      ? formatDistanceToNow(new Date(item.last_message_at), {
                          addSuffix: true,
                        })
                      : `${item.member_count} members`}
                  </small>
                </span>
                {item.unread_count ? (
                  <span className="grid size-5 place-items-center rounded-full bg-coral text-[.55rem] font-black text-white">
                    {Math.min(item.unread_count, 9)}
                  </span>
                ) : null}
              </button>
            ))}
            {!conversations.isLoading && filteredConversations.length === 0 ? (
              <p className="p-8 text-center text-xs text-muted">
                No conversations yet.
              </p>
            ) : null}
          </div>
        </aside>

        <section
          className={`${!activeConversationId ? "hidden lg:flex" : "flex"} min-w-0 flex-col`}
        >
          {selected ? (
            <>
              <div className="flex min-h-16 items-center gap-3 border-b border-line px-5">
                <button
                  onClick={() => setActive(null)}
                  className="text-xs font-bold text-coral lg:hidden"
                >
                  Back
                </button>
                <span className="grid size-9 place-items-center rounded-full bg-ink text-[.6rem] font-black text-paper">
                  {initials(selected.title ?? "Chat")}
                </span>
                <div className="min-w-0 flex-1">
                  <b className="block truncate text-xs">
                    {selected.title ?? "Conversation"}
                  </b>
                  <small className="text-[.58rem] text-emerald-600">
                    Private · live
                  </small>
                </div>
                {selected.kind === "group" ? (
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => setManaging(true)}
                    aria-label="Group settings"
                  >
                    <Settings2 className="size-4" />
                  </Button>
                ) : null}
              </div>
              <div className="scrollbar-subtle flex-1 overflow-y-auto p-4 sm:p-6">
                <div className="mx-auto grid max-w-3xl gap-3">
                  {messages.isLoading ? (
                    <LoaderCircle className="mx-auto mt-20 size-5 animate-spin text-muted" />
                  ) : null}
                  {messages.hasNextPage ? (
                    <Button
                      className="mx-auto"
                      size="sm"
                      variant="ghost"
                      disabled={messages.isFetchingNextPage}
                      onClick={() => messages.fetchNextPage()}
                    >
                      {messages.isFetchingNextPage ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : null}
                      Load older messages
                    </Button>
                  ) : null}
                  {messageItems.map((message, index) => {
                    const mine = message.sender_id === me.data?.id;
                    const showDay =
                      index === 0 ||
                      new Date(message.created_at).toDateString() !==
                        new Date(
                          messageItems[index - 1]!.created_at,
                        ).toDateString();
                    return (
                      <div key={message.id} className="group/message">
                        {showDay ? (
                          <p className="my-5 text-center text-[.58rem] font-bold text-muted">
                            {format(
                              new Date(message.created_at),
                              "d MMMM yyyy",
                            )}
                          </p>
                        ) : null}
                        <div
                          className={`flex items-end gap-1 ${mine ? "justify-end" : "justify-start"}`}
                        >
                          {mine ? (
                            <button
                              className="mb-1 p-1 text-muted opacity-0 transition group-hover/message:opacity-100 focus:opacity-100"
                              aria-label="Delete message"
                              onClick={() => {
                                if (
                                  window.confirm(
                                    "Delete this message for everyone?",
                                  )
                                ) {
                                  removeMessage.mutate(message.id);
                                }
                              }}
                            >
                              <Trash2 className="size-3.5" />
                            </button>
                          ) : null}
                          <div
                            className={`max-w-[82%] rounded-2xl px-4 py-3 ${mine ? "rounded-br-md bg-ink text-paper" : "rounded-bl-md bg-ink/5"}`}
                          >
                            {!mine ? (
                              <p className="mb-1.5 text-[.58rem] font-black text-coral">
                                {message.sender_name}
                              </p>
                            ) : null}
                            <p className="whitespace-pre-wrap text-sm leading-6">
                              {message.text}
                            </p>
                            {message.attachments?.length ? (
                              <div className="mt-2 grid gap-2">
                                {message.attachments.map((item) =>
                                  item.thumbnail_url ? (
                                    <a
                                      key={item.id}
                                      href={item.content_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="block overflow-hidden rounded-xl border border-current/10"
                                    >
                                      {/* eslint-disable-next-line @next/next/no-img-element */}
                                      <img
                                        src={item.thumbnail_url}
                                        alt={item.filename}
                                        className="max-h-64 w-full object-cover"
                                      />
                                      <span className="flex items-center gap-2 px-3 py-2 text-xs font-bold">
                                        <ImageIcon className="size-4" />
                                        <span className="truncate">
                                          {item.filename}
                                        </span>
                                      </span>
                                    </a>
                                  ) : (
                                    <a
                                      key={item.id}
                                      href={item.content_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="flex items-center gap-2 rounded-xl border border-current/10 px-3 py-2 text-xs font-bold"
                                    >
                                      <FileText className="size-4 shrink-0" />
                                      <span className="truncate">
                                        {item.filename}
                                      </span>
                                    </a>
                                  ),
                                )}
                              </div>
                            ) : null}
                            <span
                              className={`mt-1.5 flex items-center justify-end gap-1 text-[.52rem] ${mine ? "text-paper/50" : "text-muted"}`}
                            >
                              {format(new Date(message.created_at), "HH:mm")}
                              {mine ? (
                                <CheckCheck
                                  className="size-3"
                                  aria-label={
                                    message.read_by
                                      ? `Read by ${message.read_by}`
                                      : "Sent"
                                  }
                                />
                              ) : null}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={bottom} />
                </div>
              </div>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (text.trim() || attachment?.status === "ready")
                    send.mutate();
                }}
                className="border-t border-line p-3 sm:p-4"
              >
                {attachment || pendingFilePreview ? (
                  <div className="mb-2 flex items-center gap-3 rounded-xl border border-line bg-panel px-3 py-2">
                    {pendingFilePreview?.url ? (
                      <span className="relative size-14 shrink-0 overflow-hidden rounded-lg bg-ink/5">
                        <Image
                          fill
                          unoptimized
                          alt={`Preview of ${pendingFilePreview.name}`}
                          className="object-cover"
                          sizes="56px"
                          src={pendingFilePreview.url}
                        />
                      </span>
                    ) : (
                      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-coral/10">
                        <FileText className="size-4 text-coral" />
                      </span>
                    )}
                    <span className="min-w-0 flex-1">
                      <b className="block truncate text-xs">
                        {attachment?.original_filename ??
                          pendingFilePreview?.name}
                      </b>
                      <span className="text-[.6rem] text-muted">
                        {uploadAttachment.isPending
                          ? "Uploading securely…"
                          : attachment?.status === "ready"
                            ? "Ready to send"
                            : attachment?.status === "rejected"
                              ? "Rejected by security scan"
                              : "Security scan in progress…"}
                      </span>
                    </span>
                    {uploadAttachment.isPending ||
                    (attachment &&
                      ["quarantined", "scanning"].includes(
                        attachment.status,
                      )) ? (
                      <LoaderCircle className="size-4 animate-spin text-muted" />
                    ) : null}
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      disabled={uploadAttachment.isPending}
                      aria-label="Remove attachment"
                      onClick={() => {
                        setPendingAttachment(null);
                        setPendingFilePreview(null);
                      }}
                    >
                      <X className="size-4" />
                    </Button>
                  </div>
                ) : null}
                <div className="flex items-end gap-2">
                  <input
                    ref={fileInput}
                    type="file"
                    className="sr-only"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        setPendingFilePreview({
                          name: file.name,
                          url: file.type.startsWith("image/")
                            ? URL.createObjectURL(file)
                            : "",
                        });
                        uploadAttachment.mutate(file);
                      }
                      event.target.value = "";
                    }}
                  />
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    disabled={
                      uploadAttachment.isPending ||
                      Boolean(
                        attachment &&
                        ["quarantined", "scanning"].includes(attachment.status),
                      )
                    }
                    onClick={() => fileInput.current?.click()}
                    aria-label="Attach a file"
                  >
                    {uploadAttachment.isPending ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <Paperclip className="size-4" />
                    )}
                  </Button>
                  <textarea
                    rows={1}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        if (text.trim() || attachment?.status === "ready")
                          send.mutate();
                      }
                    }}
                    placeholder="Write a private message"
                    className="max-h-32 min-h-11 flex-1 resize-none rounded-xl border border-line bg-panel px-4 py-3 text-sm outline-none focus:border-ink/25"
                  />
                  <Button
                    size="icon"
                    disabled={
                      send.isPending ||
                      (!text.trim() && attachment?.status !== "ready") ||
                      Boolean(
                        attachment &&
                        ["quarantined", "scanning", "rejected"].includes(
                          attachment.status,
                        ),
                      )
                    }
                    aria-label="Send message"
                  >
                    {send.isPending ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <Send className="size-4" />
                    )}
                  </Button>
                </div>
              </form>
            </>
          ) : (
            <div className="m-auto max-w-sm p-8 text-center">
              <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-ink/5">
                <Users className="size-6 text-muted" />
              </span>
              <h3 className="mt-5 font-black">Start a member conversation</h3>
              <p className="mt-2 text-xs leading-5 text-muted">
                Choose an existing conversation or create a direct chat or
                member group.
              </p>
            </div>
          )}
        </section>
      </Card>

      {creating ? (
        <NewConversationDialog close={() => setCreating(false)} />
      ) : null}
      {managing && selected && me.data ? (
        <GroupPanel
          conversation={selected}
          meId={me.data.id}
          close={() => setManaging(false)}
        />
      ) : null}
    </div>
  );
}
