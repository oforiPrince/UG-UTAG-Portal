"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Eye,
  FileWarning,
  LoaderCircle,
  RotateCcw,
  X,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { humanize } from "@/lib/utils";

type ModerationStatus =
  | "all"
  | "review"
  | "scheduled"
  | "published"
  | "draft"
  | "withdrawn"
  | "archived";
type ModerationDecision = "approve" | "changes_requested" | "withdraw";
type ModerationItem = {
  id: string;
  kind: "news" | "announcement" | "event" | "document" | "gallery";
  title: string;
  summary: string;
  status: string;
  updated_at: string;
  version: number | null;
  public_url: string | null;
  workspace_url: string;
};

const filters: { value: ModerationStatus; label: string }[] = [
  { value: "review", label: "Needs review" },
  { value: "scheduled", label: "Scheduled" },
  { value: "published", label: "Published" },
  { value: "draft", label: "Drafts" },
  { value: "all", label: "All content" },
];

function previewUrl(item: ModerationItem) {
  return `/dashboard/preview/${item.kind}/${item.id}`;
}

export function ModerationClient() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ModerationStatus>("review");
  const [decision, setDecision] = useState<{
    item: ModerationItem;
    value: ModerationDecision;
  }>();
  const [note, setNote] = useState("");
  const queue = useQuery({
    queryKey: ["moderation"],
    queryFn: () => api<ModerationItem[]>("/api/v1/moderation"),
  });
  const visible = useMemo(
    () =>
      (queue.data ?? []).filter((item) => status === "all" || item.status === status),
    [queue.data, status],
  );
  const counts = useMemo(
    () =>
      (queue.data ?? []).reduce<Record<string, number>>((result, item) => {
        result[item.status] = (result[item.status] ?? 0) + 1;
        return result;
      }, {}),
    [queue.data],
  );
  const saveDecision = useMutation({
    mutationFn: ({ item, value }: { item: ModerationItem; value: ModerationDecision }) =>
      api<ModerationItem>(`/api/v1/moderation/${item.kind}/${item.id}`, {
        method: "POST",
        body: {
          decision: value,
          note,
          expected_version: item.version,
        },
      }),
    onSuccess: async (_result, variables) => {
      toast.success(
        variables.value === "approve"
          ? "Content published"
          : variables.value === "changes_requested"
            ? "Content returned for changes"
            : "Content withdrawn",
      );
      await queryClient.invalidateQueries({ queryKey: ["moderation"] });
      setDecision(undefined);
      setNote("");
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Moderation action failed"),
  });

  return (
    <div className="grid gap-5">
      <header className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow text-coral">Public content control</p>
          <h2 className="display-type mt-3 text-4xl sm:text-5xl">Moderation queue</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
            Review public-site news, events, documents and galleries before release. Every
            decision is version-checked and recorded in the audit ledger.
          </p>
        </div>
        <div className="rounded-2xl border border-line bg-panel px-5 py-3">
          <span className="block text-[.62rem] font-black tracking-wide text-muted uppercase">
            Awaiting review
          </span>
          <strong className="mt-1 block text-2xl font-black text-coral">{counts.review ?? 0}</strong>
        </div>
      </header>

      <div className="scrollbar-subtle flex gap-2 overflow-x-auto pb-1" role="tablist">
        {filters.map((filter) => (
          <button
            key={filter.value}
            type="button"
            role="tab"
            aria-selected={status === filter.value}
            onClick={() => setStatus(filter.value)}
            className={`min-h-10 shrink-0 rounded-full border px-4 text-xs font-bold transition ${
              status === filter.value
                ? "border-ink bg-ink text-paper"
                : "border-line bg-panel text-muted hover:text-ink"
            }`}
          >
            {filter.label}
            {filter.value !== "all" ? ` · ${counts[filter.value] ?? 0}` : ""}
          </button>
        ))}
      </div>

      {queue.isLoading ? (
        <div className="grid gap-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="h-36 animate-pulse rounded-2xl bg-ink/5" />
          ))}
        </div>
      ) : queue.error ? (
        <Card>
          <CardContent className="py-16 text-center">
            <FileWarning className="mx-auto size-8 text-coral" />
            <p className="mt-4 font-black">The moderation queue could not be loaded.</p>
            <button className="mt-3 text-sm font-bold text-coral" onClick={() => queue.refetch()}>
              Try again
            </button>
          </CardContent>
        </Card>
      ) : visible.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <CheckCircle2 className="mx-auto size-8 text-emerald-600" />
            <p className="mt-4 font-black">Nothing in {humanize(status)}.</p>
            <p className="mt-2 text-xs text-muted">New submissions will appear here automatically.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {visible.map((item) => {
            const preview = previewUrl(item);
            return (
              <Card key={`${item.kind}-${item.id}`}>
                <CardContent className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-coral/10 px-2.5 py-1 text-[.62rem] font-black text-coral uppercase">
                        {humanize(item.kind)}
                      </span>
                      <span className="rounded-full bg-ink/5 px-2.5 py-1 text-[.62rem] font-bold text-muted">
                        {humanize(item.status)}
                      </span>
                      <span className="inline-flex items-center gap-1 text-[.62rem] text-muted">
                        <Clock3 className="size-3" />
                        {formatDistanceToNow(new Date(item.updated_at), { addSuffix: true })}
                      </span>
                    </div>
                    <h3 className="mt-3 text-lg font-black">{item.title}</h3>
                    <p className="mt-2 line-clamp-2 max-w-4xl text-xs leading-6 text-muted">
                      {item.summary || "No summary has been provided."}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <Button asChild size="sm" variant="outline">
                      <Link href={preview} target="_blank" rel="noreferrer">
                        <Eye className="size-4" /> Preview
                      </Link>
                    </Button>
                    <Button asChild size="sm" variant="ghost">
                      <Link href={item.workspace_url}>
                        Edit <ArrowUpRight className="size-4" />
                      </Link>
                    </Button>
                    {item.status === "review" ? (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setNote("");
                            setDecision({ item, value: "changes_requested" });
                          }}
                        >
                          <RotateCcw className="size-4" /> Return
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => {
                            setNote("");
                            setDecision({ item, value: "approve" });
                          }}
                        >
                          <CheckCircle2 className="size-4" /> Publish
                        </Button>
                      </>
                    ) : null}
                    {item.status === "published" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-red-500/30 text-red-700"
                        onClick={() => {
                          setNote("");
                          setDecision({ item, value: "withdraw" });
                        }}
                      >
                        Withdraw
                      </Button>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {decision ? (
        <div
          className="fixed inset-0 z-[90] grid place-items-center bg-black/45 p-4 backdrop-blur-sm"
          onMouseDown={() => setDecision(undefined)}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Confirm moderation decision"
            className="w-full max-w-lg rounded-2xl border border-line bg-paper p-6 shadow-2xl sm:p-8"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="eyebrow text-coral">Moderation decision</p>
                <h2 className="mt-3 text-2xl font-black">
                  {decision.value === "approve"
                    ? "Publish this content?"
                    : decision.value === "changes_requested"
                      ? "Return for changes"
                      : "Withdraw from the public site"}
                </h2>
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label="Close moderation dialog"
                onClick={() => setDecision(undefined)}
              >
                <X className="size-5" />
              </Button>
            </div>
            <p className="mt-3 text-sm text-muted">{decision.item.title}</p>
            <label className="mt-6 grid gap-2 text-xs font-bold">
              Decision note {decision.value === "approve" ? "(optional)" : "(required)"}
              <textarea
                autoFocus
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={
                  decision.value === "approve"
                    ? "Optional internal publication note"
                    : "Give the editor a clear, actionable reason"
                }
                className="min-h-32 rounded-xl border border-line bg-panel p-4 text-sm font-normal outline-none focus:border-sky"
              />
            </label>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDecision(undefined)}>
                Cancel
              </Button>
              <Button
                disabled={
                  saveDecision.isPending ||
                  (decision.value !== "approve" && note.trim().length === 0)
                }
                onClick={() =>
                  saveDecision.mutate({ item: decision.item, value: decision.value })
                }
              >
                {saveDecision.isPending ? <LoaderCircle className="size-4 animate-spin" /> : null}
                Confirm decision
              </Button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
