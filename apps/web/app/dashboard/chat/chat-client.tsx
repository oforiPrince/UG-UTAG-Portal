"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";
import {
  ArrowLeft,
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Copy,
  Edit3,
  FileText,
  Image as ImageIcon,
  Info,
  Link2,
  LoaderCircle,
  MessageSquarePlus,
  Paperclip,
  Reply,
  Search,
  Send,
  Settings2,
  Trash2,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import Image from "next/image";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useRealtime } from "@/components/realtime-provider";
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
  display_title: string;
  direct_member_id: string | null;
  current_user_role: "owner" | "admin" | "member";
  is_muted: boolean;
  last_message_preview: string | null;
  last_message_sender: string | null;
};
type MessageReply = {
  id: string;
  sender_id: string;
  sender_name: string;
  text: string;
};
type Message = {
  id: string;
  sender_id: string;
  sender_name: string;
  text: string;
  created_at: string;
  edited_at: string | null;
  client_message_id: string;
  reply_to_id: string | null;
  reply_to: MessageReply | null;
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
type PendingChatAttachment = {
  key: string;
  name: string;
  previewUrl: string;
  upload: ChatUpload | null;
  error: string | null;
};
type Invite = {
  id: string;
  join_url: string;
  conversation_title: string;
  expires_at: string;
};

function subscribeDesktopLayout(onChange: () => void) {
  const media = window.matchMedia("(min-width: 1024px)");
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

function useDesktopLayout() {
  return useSyncExternalStore(
    subscribeDesktopLayout,
    () => window.matchMedia("(min-width: 1024px)").matches,
    () => true,
  );
}

function NewConversationDialog({
  close,
  onCreated,
}: {
  close: () => void;
  onCreated: (conversation: Conversation) => void;
}) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<"direct" | "group">("direct");
  const [title, setTitle] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [close]);
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
    onSuccess: async (conversation) => {
      await queryClient.invalidateQueries({
        queryKey: ["chat", "conversations"],
      });
      toast.success(
        kind === "group" ? "Group created" : "Conversation started",
      );
      onCreated(conversation);
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
              autoFocus
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
  onLeft,
}: {
  conversation: Conversation;
  meId: string;
  close: () => void;
  onLeft: () => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(conversation.title ?? "");
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [inviteUrl, setInviteUrl] = useState("");
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [close]);
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
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["chat", "members", conversation.id],
        }),
        queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }),
      ]);
      setSelected([]);
      if (
        variables.method === "DELETE" &&
        variables.endpoint.endsWith(`/members/${meId}`)
      ) {
        onLeft();
      }
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
                {canManage &&
                member.role !== "owner" &&
                member.user_id !== meId ? (
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
        ) : null}
        {me && me.role !== "owner" ? (
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
  const realtime = useRealtime();
  const isDesktop = useDesktopLayout();
  const [active, setActive] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [messageSearch, setMessageSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [managing, setManaging] = useState(false);
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingChatAttachment[]
  >([]);
  const [inviteToken, setInviteToken] = useState(initialInvite);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const pendingAttachmentsRef = useRef<PendingChatAttachment[]>([]);
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
    return (conversations.data ?? []).filter((item) => {
      const haystack = [
        item.display_title,
        item.last_message_sender,
        item.last_message_preview,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [conversations.data, search]);
  const activeExists = Boolean(
    active && conversations.data?.some((item) => item.id === active),
  );
  const activeConversationId = activeExists
    ? active
    : isDesktop
      ? (conversations.data?.[0]?.id ?? null)
      : null;
  const text = activeConversationId ? (drafts[activeConversationId] ?? "") : "";
  const setText = (value: string) => {
    if (!activeConversationId) return;
    setDrafts((current) => ({ ...current, [activeConversationId]: value }));
  };
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
  const visibleMessageItems = useMemo(() => {
    const needle = messageSearch.trim().toLowerCase();
    if (!needle) return messageItems;
    return messageItems.filter((message) =>
      [message.text, message.sender_name, message.reply_to?.text]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [messageItems, messageSearch]);
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
  const attachmentsReady =
    pendingAttachments.length > 0 &&
    pendingAttachments.every((item) => item.upload?.status === "ready");
  const attachmentsBusy = pendingAttachments.some(
    (item) =>
      item.upload === null ||
      ["quarantined", "scanning"].includes(item.upload.status),
  );
  const attachmentsRejected = pendingAttachments.some(
    (item) => item.error !== null || item.upload?.status === "rejected",
  );
  const scanningUploadKey = pendingAttachments
    .filter(
      (item) =>
        item.upload && ["quarantined", "scanning"].includes(item.upload.status),
    )
    .map((item) => `${item.key}:${item.upload!.status}`)
    .join("|");

  useEffect(() => {
    pendingAttachmentsRef.current = pendingAttachments;
  }, [pendingAttachments]);

  useEffect(() => () => {
    for (const item of pendingAttachmentsRef.current) {
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    }
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversationId, latestMessageId]);

  useEffect(() => {
    if (!activeConversationId || !latestMessageId) return;
    api(`/api/v1/chat/conversations/${activeConversationId}/read`, {
      method: "POST",
    })
      .then(() =>
        queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] }),
      )
      .catch(() => undefined);
  }, [activeConversationId, latestMessageId, queryClient]);

  useEffect(() => {
    if (!scanningUploadKey) return;
    let cancelled = false;
    const poll = async () => {
      const scanning = pendingAttachmentsRef.current.filter(
        (item) =>
          item.upload &&
          ["quarantined", "scanning"].includes(item.upload.status),
      );
      const updates = await Promise.all(
        scanning.map(async (item) => ({
          key: item.key,
          upload: await api<ChatUpload>(
            `/api/v1/chat/attachments/uploads/${item.upload!.id}`,
          ).catch(() => item.upload!),
        })),
      );
      if (cancelled) return;
      const byKey = new Map(updates.map((item) => [item.key, item.upload]));
      setPendingAttachments((current) =>
        current.map((item) => ({
          ...item,
          upload: byKey.get(item.key) ?? item.upload,
        })),
      );
    };
    void poll();
    const timer = window.setInterval(poll, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [scanningUploadKey]);

  const uploadAttachment = useMutation({
    mutationFn: async (files: { key: string; file: File }[]) =>
      Promise.all(
        files.map(async ({ key, file }) => {
          const body = new FormData();
          body.append("file", file);
          try {
            const upload = await api<ChatUpload>("/api/v1/chat/attachments", {
              method: "POST",
              body,
            });
            return { key, upload, error: null };
          } catch (error) {
            return {
              key,
              upload: null,
              error:
                error instanceof Error
                  ? error.message
                  : "Attachment could not upload",
            };
          }
        }),
      ),
    onSuccess: (results) => {
      const byKey = new Map(results.map((item) => [item.key, item]));
      setPendingAttachments((current) =>
        current.map((item) => {
          const result = byKey.get(item.key);
          return result
            ? { ...item, upload: result.upload, error: result.error }
            : item;
        }),
      );
      const failed = results.filter((item) => item.error).length;
      if (failed) toast.error(`${failed} attachment(s) could not be uploaded`);
      if (failed < results.length) {
        toast.success("Attachment security scanning has started");
      }
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
      selectConversation(conversation.id);
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
            reply_to_id: replyingTo?.id ?? null,
            attachment_media_ids: pendingAttachments
              .filter((item) => item.upload?.status === "ready")
              .map((item) => item.upload!.id),
          },
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["chat", "messages", activeConversationId],
      });
      if (activeConversationId) {
        setDrafts((current) => {
          const next = { ...current };
          delete next[activeConversationId];
          return next;
        });
      }
      setReplyingTo(null);
      for (const item of pendingAttachments) {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      }
      setPendingAttachments([]);
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

  const editMessage = useMutation({
    mutationFn: ({ messageId, value }: { messageId: string; value: string }) =>
      api<Message>(`/api/v1/chat/messages/${messageId}`, {
        method: "PATCH",
        body: { text: value },
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["chat", "messages", activeConversationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["chat", "conversations"],
        }),
      ]);
      setEditingMessageId(null);
      setEditText("");
      toast.success("Message updated");
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Could not update message",
      ),
  });

  const updatePreference = useMutation({
    mutationFn: ({
      conversationId,
      isMuted,
    }: {
      conversationId: string;
      isMuted: boolean;
    }) =>
      api<Conversation>(
        `/api/v1/chat/conversations/${conversationId}/preferences`,
        { method: "PATCH", body: { is_muted: isMuted } },
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData<Conversation[]>(
        ["chat", "conversations"],
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)),
      );
      toast.success(
        updated.is_muted ? "Conversation muted" : "Conversation unmuted",
      );
    },
    onError: (error) =>
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not update conversation preferences",
      ),
  });

  function queueAttachments(fileList: FileList | File[]) {
    const remaining = Math.max(0, 5 - pendingAttachments.length);
    const files = Array.from(fileList).slice(0, remaining);
    if (!files.length) {
      toast.error("You can attach up to 5 files to one message");
      return;
    }
    if (Array.from(fileList).length > remaining) {
      toast.error(`Only ${remaining} more attachment(s) can be added`);
    }
    const entries = files.map((file) => ({
      key: crypto.randomUUID(),
      name: file.name,
      previewUrl: file.type.startsWith("image/")
        ? URL.createObjectURL(file)
        : "",
      upload: null,
      error: null,
      file,
    }));
    setPendingAttachments((current) => [
      ...current,
      ...entries.map((entry) => ({
        key: entry.key,
        name: entry.name,
        previewUrl: entry.previewUrl,
        upload: entry.upload,
        error: entry.error,
      })),
    ]);
    uploadAttachment.mutate(
      entries.map((entry) => ({ key: entry.key, file: entry.file })),
    );
  }

  function removePendingAttachment(key: string) {
    setPendingAttachments((current) => {
      const removed = current.find((item) => item.key === key);
      if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return current.filter((item) => item.key !== key);
    });
  }

  function selectConversation(conversationId: string | null) {
    if (conversationId === active) return;
    setReplyingTo(null);
    setEditingMessageId(null);
    setEditText("");
    setMessageSearch("");
    for (const item of pendingAttachmentsRef.current) {
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    }
    setPendingAttachments([]);
    setActive(conversationId);
  }

  return (
    <div className="grid gap-5">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow text-coral">Private communications</p>
          <h2 className="display-type mt-3 text-4xl sm:text-5xl">
            Member chat
          </h2>
          <div className="mt-3 flex items-center gap-2 text-sm text-muted">
            <span
              className={`size-2 rounded-full ${
                realtime.state === "live"
                  ? "bg-emerald-500"
                  : realtime.state === "connecting"
                    ? "animate-pulse bg-gold"
                    : "bg-muted/50"
              }`}
            />
            {realtime.state === "live"
              ? "Messages update live"
              : realtime.state === "connecting"
                ? "Connecting to live updates…"
                : "Offline — messages will sync when reconnected"}
          </div>
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

      <Card className="grid h-[calc(100dvh-11rem)] min-h-[38rem] max-h-[56rem] overflow-hidden lg:grid-cols-[20rem_1fr]">
        <aside
          className={`${activeExists ? "hidden lg:block" : "block"} min-h-0 border-r border-line`}
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
          <div className="scrollbar-subtle h-[calc(100%-4.1rem)] divide-y divide-line overflow-y-auto">
            {conversations.isLoading ? (
              <div className="grid place-items-center gap-3 p-12 text-center">
                <LoaderCircle className="size-5 animate-spin text-muted" />
                <p className="text-xs text-muted">Loading conversations…</p>
              </div>
            ) : null}
            {conversations.isError ? (
              <div className="grid gap-3 p-6 text-center">
                <p className="text-xs leading-5 text-muted">
                  Conversations could not be loaded.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => conversations.refetch()}
                >
                  Try again
                </Button>
              </div>
            ) : null}
            {filteredConversations.map((item) => (
              <button
                key={item.id}
                onClick={() => selectConversation(item.id)}
                className={`relative flex w-full items-center gap-3 p-4 text-left transition hover:bg-ink/[.025] ${activeConversationId === item.id ? "bg-ink/[.05]" : ""}`}
              >
                {activeConversationId === item.id ? (
                  <span className="absolute inset-y-3 left-0 w-0.5 rounded-full bg-coral" />
                ) : null}
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-ink text-[.62rem] font-black text-paper">
                  {initials(item.display_title)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <b className="block min-w-0 flex-1 truncate text-xs">
                      {item.display_title}
                    </b>
                    {item.is_muted ? (
                      <BellOff
                        className="size-3 shrink-0 text-muted"
                        aria-label="Muted"
                      />
                    ) : null}
                  </span>
                  <small className="mt-1 flex min-w-0 items-center gap-1 text-[.6rem] text-muted">
                    <span className="truncate">
                      {item.last_message_preview
                        ? `${item.last_message_sender}: ${item.last_message_preview}`
                        : item.kind === "group"
                          ? `${item.member_count} members · No messages yet`
                          : "No messages yet"}
                    </span>
                    {item.last_message_at ? (
                      <span className="shrink-0" aria-hidden="true">
                        ·
                      </span>
                    ) : null}
                    {item.last_message_at ? (
                      <span className="shrink-0">
                        {formatDistanceToNow(new Date(item.last_message_at))}
                      </span>
                    ) : null}
                  </small>
                </span>
                {item.unread_count ? (
                  <span className="grid min-w-5 place-items-center rounded-full bg-coral px-1.5 py-1 text-[.55rem] font-black text-white">
                    {item.unread_count > 99 ? "99+" : item.unread_count}
                  </span>
                ) : null}
              </button>
            ))}
            {!conversations.isLoading &&
            !conversations.isError &&
            filteredConversations.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-xs text-muted">
                  {search
                    ? "No conversations match your search."
                    : "No conversations yet."}
                </p>
                {!search ? (
                  <Button
                    className="mt-4"
                    size="sm"
                    variant="outline"
                    onClick={() => setCreating(true)}
                  >
                    Start one
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>
        </aside>

        <section
          className={`${!activeConversationId ? "hidden lg:flex" : "flex"} min-h-0 min-w-0 flex-col`}
        >
          {selected ? (
            <>
              <div className="flex min-h-16 items-center gap-3 border-b border-line px-5">
                <Button
                  onClick={() => selectConversation(null)}
                  size="icon"
                  variant="ghost"
                  className="-ml-2 lg:hidden"
                  aria-label="Back to conversations"
                >
                  <ArrowLeft className="size-4" />
                </Button>
                <span className="grid size-9 place-items-center rounded-full bg-ink text-[.6rem] font-black text-paper">
                  {initials(selected.display_title)}
                </span>
                <div className="min-w-0 flex-1">
                  <b className="block truncate text-xs">
                    {selected.display_title}
                  </b>
                  <small className="text-[.58rem] text-muted">
                    {selected.kind === "group"
                      ? `${selected.member_count} members`
                      : "Direct conversation"}
                    {selected.is_muted ? " · Muted" : ""}
                  </small>
                </div>
                <label className="hidden min-h-9 w-44 items-center gap-2 rounded-xl bg-ink/5 px-3 md:flex">
                  <Search className="size-3.5 text-muted" />
                  <span className="sr-only">Search loaded messages</span>
                  <input
                    value={messageSearch}
                    onChange={(event) => setMessageSearch(event.target.value)}
                    className="min-w-0 flex-1 bg-transparent text-[.68rem] outline-none"
                    placeholder="Search messages"
                  />
                  {messageSearch ? (
                    <button
                      type="button"
                      onClick={() => setMessageSearch("")}
                      aria-label="Clear message search"
                    >
                      <X className="size-3.5 text-muted" />
                    </button>
                  ) : null}
                </label>
                <Button
                  size="icon"
                  variant="ghost"
                  disabled={updatePreference.isPending}
                  onClick={() =>
                    updatePreference.mutate({
                      conversationId: selected.id,
                      isMuted: !selected.is_muted,
                    })
                  }
                  aria-label={
                    selected.is_muted
                      ? "Unmute conversation"
                      : "Mute conversation"
                  }
                  title={
                    selected.is_muted
                      ? "Unmute conversation"
                      : "Mute conversation"
                  }
                >
                  {selected.is_muted ? (
                    <BellOff className="size-4" />
                  ) : (
                    <Bell className="size-4" />
                  )}
                </Button>
                {selected.kind === "group" ? (
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => setManaging(true)}
                    aria-label="Group settings"
                  >
                    <Settings2 className="size-4" />
                  </Button>
                ) : (
                  <span
                    className="hidden size-11 place-items-center text-muted sm:grid"
                    title="Encrypted private conversation"
                  >
                    <Info className="size-4" />
                  </span>
                )}
              </div>
              <div className="scrollbar-subtle min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
                <div className="mx-auto grid max-w-3xl gap-3">
                  <label className="flex min-h-10 items-center gap-2 rounded-xl bg-ink/5 px-3 md:hidden">
                    <Search className="size-3.5 text-muted" />
                    <span className="sr-only">Search loaded messages</span>
                    <input
                      value={messageSearch}
                      onChange={(event) => setMessageSearch(event.target.value)}
                      className="min-w-0 flex-1 bg-transparent text-xs outline-none"
                      placeholder="Search loaded messages"
                    />
                    {messageSearch ? (
                      <button
                        type="button"
                        onClick={() => setMessageSearch("")}
                        aria-label="Clear message search"
                      >
                        <X className="size-3.5 text-muted" />
                      </button>
                    ) : null}
                  </label>
                  {messages.isLoading ? (
                    <div className="grid place-items-center gap-3 py-20">
                      <LoaderCircle className="size-5 animate-spin text-muted" />
                      <p className="text-xs text-muted">Loading messages…</p>
                    </div>
                  ) : null}
                  {messages.isError ? (
                    <div className="grid place-items-center gap-3 py-16 text-center">
                      <p className="text-xs text-muted">
                        Messages could not be loaded.
                      </p>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => messages.refetch()}
                      >
                        Try again
                      </Button>
                    </div>
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
                  {!messages.isLoading &&
                  !messages.isError &&
                  messageItems.length === 0 ? (
                    <div className="mx-auto max-w-sm py-20 text-center">
                      <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-ink/5">
                        <Send className="size-5 text-muted" />
                      </span>
                      <h3 className="mt-4 text-sm font-black">
                        Start the conversation
                      </h3>
                      <p className="mt-2 text-xs leading-5 text-muted">
                        Messages and attachments shared here are encrypted at
                        rest.
                      </p>
                    </div>
                  ) : null}
                  {messageSearch && visibleMessageItems.length === 0 ? (
                    <div className="py-16 text-center text-xs text-muted">
                      No loaded messages match “{messageSearch}”. Load older
                      messages to search further back.
                    </div>
                  ) : null}
                  {visibleMessageItems.map((message, index) => {
                    const mine = message.sender_id === me.data?.id;
                    const showDay =
                      index === 0 ||
                      new Date(message.created_at).toDateString() !==
                        new Date(
                          visibleMessageItems[index - 1]!.created_at,
                        ).toDateString();
                    return (
                      <div
                        key={message.id}
                        id={`message-${message.id}`}
                        className="group/message scroll-mt-6"
                      >
                        {showDay ? (
                          <p className="my-5 text-center text-[.58rem] font-bold text-muted">
                            {format(
                              new Date(message.created_at),
                              "d MMMM yyyy",
                            )}
                          </p>
                        ) : null}
                        <div
                          className={`flex items-end gap-1.5 ${mine ? "justify-end" : "justify-start"}`}
                        >
                          <span className="mb-1 flex items-center text-muted opacity-60 transition sm:opacity-0 sm:group-hover/message:opacity-100 sm:group-focus-within/message:opacity-100">
                            <button
                              className="rounded-md p-1.5 hover:bg-ink/5"
                              aria-label="Reply to message"
                              title="Reply"
                              onClick={() => setReplyingTo(message)}
                            >
                              <Reply className="size-3.5" />
                            </button>
                            {mine ? (
                              <button
                                className="rounded-md p-1.5 hover:bg-ink/5"
                                aria-label="Edit message"
                                title="Edit"
                                onClick={() => {
                                  setEditingMessageId(message.id);
                                  setEditText(message.text);
                                }}
                              >
                                <Edit3 className="size-3.5" />
                              </button>
                            ) : null}
                            {mine ? (
                              <button
                                className="rounded-md p-1.5 hover:bg-ink/5"
                                aria-label="Delete message"
                                title="Delete"
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
                          </span>
                          <div
                            className={`max-w-[82%] rounded-2xl px-4 py-3 ${mine ? "rounded-br-md bg-ink text-paper" : "rounded-bl-md bg-ink/5"}`}
                          >
                            {!mine ? (
                              <p className="mb-1.5 text-[.58rem] font-black text-coral">
                                {message.sender_name}
                              </p>
                            ) : null}
                            {message.reply_to ? (
                              <button
                                type="button"
                                onClick={() => {
                                  document
                                    .getElementById(
                                      `message-${message.reply_to!.id}`,
                                    )
                                    ?.scrollIntoView({
                                      behavior: "smooth",
                                      block: "center",
                                    });
                                }}
                                className={`mb-2 block w-full rounded-lg border-l-2 px-3 py-2 text-left ${mine ? "border-paper/40 bg-paper/8" : "border-coral/50 bg-paper/60 dark:bg-paper/30"}`}
                              >
                                <span className="block text-[.56rem] font-black opacity-70">
                                  {message.reply_to.sender_name}
                                </span>
                                <span className="mt-0.5 block truncate text-[.65rem] opacity-70">
                                  {message.reply_to.text || "Attachment"}
                                </span>
                              </button>
                            ) : message.reply_to_id ? (
                              <div className="mb-2 rounded-lg border-l-2 border-current/20 px-3 py-2 text-[.62rem] opacity-60">
                                Original message is unavailable
                              </div>
                            ) : null}
                            {editingMessageId === message.id ? (
                              <form
                                className="grid gap-2"
                                onSubmit={(event) => {
                                  event.preventDefault();
                                  if (
                                    editText.trim() ||
                                    message.attachments.length
                                  )
                                    editMessage.mutate({
                                      messageId: message.id,
                                      value: editText,
                                    });
                                }}
                              >
                                <textarea
                                  autoFocus
                                  aria-label="Edit message"
                                  rows={2}
                                  value={editText}
                                  style={{
                                    color: "var(--paper)",
                                    caretColor: "var(--paper)",
                                  }}
                                  onChange={(event) =>
                                    setEditText(event.target.value)
                                  }
                                  onKeyDown={(event) => {
                                    if (event.key === "Escape") {
                                      setEditingMessageId(null);
                                      setEditText("");
                                    }
                                  }}
                                  className="min-h-16 resize-none rounded-lg border border-current/15 bg-paper/10 px-3 py-2 text-sm outline-none focus:border-current/35"
                                />
                                <span className="flex justify-end gap-2">
                                  <button
                                    type="button"
                                    className="text-[.62rem] font-bold opacity-70"
                                    onClick={() => {
                                      setEditingMessageId(null);
                                      setEditText("");
                                    }}
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    disabled={
                                      editMessage.isPending ||
                                      (!editText.trim() &&
                                        message.attachments.length === 0)
                                    }
                                    className="rounded-full bg-paper px-3 py-1 text-[.62rem] font-black text-ink disabled:opacity-50"
                                  >
                                    {editMessage.isPending ? "Saving…" : "Save"}
                                  </button>
                                </span>
                              </form>
                            ) : message.text ? (
                              <p className="whitespace-pre-wrap text-sm leading-6">
                                {message.text}
                              </p>
                            ) : null}
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
                              {message.edited_at ? " · edited" : null}
                              {mine ? (
                                message.read_by ? (
                                  <CheckCheck
                                    className="size-3"
                                    aria-label={`Read by ${message.read_by}`}
                                  />
                                ) : (
                                  <Check className="size-3" aria-label="Sent" />
                                )
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
                  if (
                    !send.isPending &&
                    !attachmentsBusy &&
                    !attachmentsRejected &&
                    (text.trim() || attachmentsReady)
                  )
                    send.mutate();
                }}
                className="border-t border-line px-3 pt-3 pb-[calc(6rem+env(safe-area-inset-bottom))] sm:px-4 sm:pt-4 lg:p-4"
              >
                {replyingTo ? (
                  <div className="mb-2 flex items-center gap-3 rounded-xl border-l-2 border-coral bg-ink/[.035] px-3 py-2">
                    <Reply className="size-4 shrink-0 text-coral" />
                    <span className="min-w-0 flex-1">
                      <b className="block text-[.62rem] text-coral">
                        Replying to {replyingTo.sender_name}
                      </b>
                      <span className="mt-0.5 block truncate text-xs text-muted">
                        {replyingTo.text ||
                          replyingTo.attachments[0]?.filename ||
                          "Attachment"}
                      </span>
                    </span>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="size-9 min-h-9"
                      aria-label="Cancel reply"
                      onClick={() => setReplyingTo(null)}
                    >
                      <X className="size-4" />
                    </Button>
                  </div>
                ) : null}
                {pendingAttachments.length ? (
                  <div className="mb-2 grid gap-2 sm:grid-cols-2">
                    {pendingAttachments.map((item) => (
                      <div
                        key={item.key}
                        className="flex min-w-0 items-center gap-3 rounded-xl border border-line bg-panel px-3 py-2"
                      >
                        {item.previewUrl ? (
                          <span className="relative size-12 shrink-0 overflow-hidden rounded-lg bg-ink/5">
                            <Image
                              fill
                              unoptimized
                              alt={`Preview of ${item.name}`}
                              className="object-cover"
                              sizes="48px"
                              src={item.previewUrl}
                            />
                          </span>
                        ) : (
                          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-coral/10">
                            <FileText className="size-4 text-coral" />
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          <b className="block truncate text-xs">{item.name}</b>
                          <span
                            className={`text-[.6rem] ${item.error || item.upload?.status === "rejected" ? "text-red-600 dark:text-red-300" : "text-muted"}`}
                          >
                            {item.error
                              ? item.error
                              : item.upload?.status === "ready"
                                ? "Ready to send"
                                : item.upload?.status === "rejected"
                                  ? "Rejected by security scan"
                                  : item.upload
                                    ? "Security scan in progress…"
                                    : "Uploading securely…"}
                          </span>
                        </span>
                        {!item.upload ||
                        ["quarantined", "scanning"].includes(
                          item.upload.status,
                        ) ? (
                          <LoaderCircle className="size-4 shrink-0 animate-spin text-muted" />
                        ) : null}
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="size-9 min-h-9 shrink-0"
                          aria-label={`Remove ${item.name}`}
                          onClick={() => removePendingAttachment(item.key)}
                        >
                          <X className="size-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="flex items-end gap-2">
                  <input
                    ref={fileInput}
                    type="file"
                    multiple
                    className="sr-only"
                    onChange={(event) => {
                      if (event.target.files?.length)
                        queueAttachments(event.target.files);
                      event.target.value = "";
                    }}
                  />
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    disabled={pendingAttachments.length >= 5}
                    onClick={() => fileInput.current?.click()}
                    aria-label="Attach a file"
                  >
                    <Paperclip className="size-4" />
                  </Button>
                  <textarea
                    rows={1}
                    aria-label="Message"
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Escape" && replyingTo) {
                        setReplyingTo(null);
                        return;
                      }
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        if (
                          !send.isPending &&
                          !attachmentsBusy &&
                          !attachmentsRejected &&
                          (text.trim() || attachmentsReady)
                        )
                          send.mutate();
                      }
                    }}
                    placeholder={
                      replyingTo
                        ? `Reply to ${replyingTo.sender_name}`
                        : `Message ${selected.display_title}`
                    }
                    maxLength={20_000}
                    className="max-h-32 min-h-11 flex-1 resize-none rounded-xl border border-line bg-panel px-4 py-3 text-sm outline-none focus:border-ink/25"
                  />
                  <Button
                    size="icon"
                    disabled={
                      send.isPending ||
                      (!text.trim() && !attachmentsReady) ||
                      attachmentsBusy ||
                      attachmentsRejected
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
                <div className="mt-2 flex justify-between px-1 text-[.58rem] text-muted">
                  <span>Enter to send · Shift + Enter for a new line</span>
                  {text.length > 18_000 ? (
                    <span>{text.length.toLocaleString()} / 20,000</span>
                  ) : null}
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
        <NewConversationDialog
          close={() => setCreating(false)}
          onCreated={(conversation) => selectConversation(conversation.id)}
        />
      ) : null}
      {managing && selected && me.data ? (
        <GroupPanel
          conversation={selected}
          meId={me.data.id}
          close={() => setManaging(false)}
          onLeft={() => {
            setManaging(false);
            selectConversation(null);
          }}
        />
      ) : null}
    </div>
  );
}
