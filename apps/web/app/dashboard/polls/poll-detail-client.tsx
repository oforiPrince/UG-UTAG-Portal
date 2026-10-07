"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  BellRing,
  CalendarDays,
  Check,
  CheckCheck,
  Clock3,
  Copy,
  Download,
  Edit3,
  EyeOff,
  FileText,
  Info,
  LoaderCircle,
  LockKeyhole,
  Printer,
  Radio,
  Send,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useRealtime } from "@/components/realtime-provider";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { API_URL, api } from "@/lib/api";
import {
  accraInputToUtc,
  formatPollDate,
  pollCountdown,
  pollRules,
  togglePollChoice,
  utcToAccraInput,
  type Poll,
  type PollResults,
} from "@/lib/polls";
import { cn, formatNumber } from "@/lib/utils";

import { PollResultsPanel } from "./poll-results";
import {
  PollError,
  PollLoading,
  PollStatusBadge,
  usePollBoundaryRefresh,
  usePollClock,
} from "./poll-ui";

function PollBallot({ poll }: { poll: Poll }) {
  const queryClient = useQueryClient();
  const realtime = useRealtime();
  const [selected, setSelected] = useState<string[]>(poll.my_vote ?? []);
  const [confirm, setConfirm] = useState(false);
  const rules = pollRules(poll);
  const locked = !poll.can_vote;
  const vote = useMutation({
    mutationFn: () =>
      api<Poll>(`/api/v1/polls/${poll.id}/vote`, {
        method: "PUT",
        body: { option_ids: selected },
      }),
    onSuccess: async (updated) => {
      queryClient.setQueryData(["polls", "detail", poll.id], updated);
      realtime.refreshSubscriptions();
      await queryClient.invalidateQueries({ queryKey: ["polls"] });
      setConfirm(false);
      toast.success(
        poll.has_voted ? "Your vote has been updated" : "Your vote is recorded",
      );
    },
    onError: async (error) => {
      setConfirm(false);
      toast.error(
        error instanceof Error
          ? error.message
          : "Your vote could not be recorded",
      );
      await queryClient.invalidateQueries({ queryKey: ["polls"] });
    },
  });
  const unchanged =
    selected.length === (poll.my_vote?.length ?? 0) &&
    selected.every((id) => poll.my_vote?.includes(id));
  return (
    <section className="workspace-folio rounded-[1.5rem] p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow text-coral">
          {poll.has_voted ? "Your ballot" : "Have your say"}
        </p>
        <span className="flex items-center gap-1.5 text-[.65rem] text-muted">
          <LockKeyhole className="size-3.5" />
          {poll.privacy === "named" ? "Named" : "Confidential"}
        </span>
      </div>
      <h2 className="mt-5 text-xl font-bold leading-8 sm:text-2xl sm:leading-9">
        {poll.question}
      </h2>
      {poll.description ? (
        <p className="mt-5 whitespace-pre-wrap text-sm leading-7 text-muted">
          {poll.description}
        </p>
      ) : null}
      {poll.has_voted ? (
        <div
          className="mt-6 flex items-start gap-3 rounded-2xl bg-coral/6 p-4"
          role="status"
        >
          <CheckCheck className="mt-0.5 size-5 shrink-0 text-coral" />
          <div>
            <p className="text-sm font-bold">Your vote is recorded</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              {poll.allow_vote_changes && poll.status === "open"
                ? "You can update your selection before voting closes."
                : "Your submitted choice is shown below."}
            </p>
          </div>
        </div>
      ) : null}
      <fieldset className="mt-6" disabled={locked || vote.isPending}>
        <legend className="mb-3 text-xs font-semibold text-muted">
          {poll.kind === "single"
            ? "Choose one answer"
            : `Choose up to ${poll.max_choices ?? poll.options.length} answers`}
        </legend>
        <div className="grid gap-3">
          {poll.options.map((option) => {
            const checked = selected.includes(option.id);
            const atLimit =
              poll.kind === "multiple" &&
              !checked &&
              Boolean(poll.max_choices && selected.length >= poll.max_choices);
            return (
              <label
                key={option.id}
                className={cn(
                  "flex min-h-16 items-center gap-4 rounded-2xl border px-4 py-4 transition sm:px-5",
                  locked
                    ? "cursor-default"
                    : "cursor-pointer hover:border-coral/40",
                  checked
                    ? "border-coral/50 bg-coral/5"
                    : "border-line bg-panel/35",
                )}
              >
                <input
                  type={poll.kind === "single" ? "radio" : "checkbox"}
                  name={`poll-${poll.id}`}
                  value={option.id}
                  checked={checked}
                  disabled={atLimit}
                  onChange={() =>
                    setSelected((current) =>
                      togglePollChoice(
                        current,
                        option.id,
                        poll.kind,
                        poll.max_choices,
                      ),
                    )
                  }
                  className="size-4 shrink-0 accent-[var(--coral)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-coral"
                />
                <span className="flex-1 text-sm font-semibold leading-6">
                  {option.label}
                </span>
                {checked ? (
                  <Check
                    className="size-4 shrink-0 text-coral"
                    aria-hidden="true"
                  />
                ) : null}
              </label>
            );
          })}
        </div>
      </fieldset>
      {poll.can_vote ? (
        <Button
          className="mt-6 w-full sm:w-auto"
          variant="gold"
          disabled={
            !selected.length || vote.isPending || (poll.has_voted && unchanged)
          }
          onClick={() => setConfirm(true)}
        >
          <Send className="size-4" />
          {poll.has_voted ? "Update my vote" : "Submit my vote"}
        </Button>
      ) : !poll.has_voted ? (
        <p className="mt-6 flex items-start gap-2 rounded-xl bg-panel p-4 text-sm leading-6 text-muted">
          <Info className="mt-1 size-4 shrink-0" />
          {poll.status === "scheduled"
            ? "Voting has not opened yet. Return when the voting window begins."
            : poll.status === "closed"
              ? "This voting window has closed."
              : poll.status === "draft"
                ? "This is a draft preview. Publish the poll to open voting."
                : "Your account is outside this poll’s published voting roll."}
        </p>
      ) : null}
      <div className="mt-6 grid gap-2 border-t border-line pt-5 text-xs leading-5 text-muted">
        <p>{rules.privacy}</p>
        <p>{rules.results}</p>
        <p>{rules.changes}</p>
      </div>
      <ConfirmDialog
        open={confirm}
        title={
          poll.has_voted ? "Update your ballot?" : "Ready to cast your vote?"
        }
        description={`${poll.options
          .filter((option) => selected.includes(option.id))
          .map((option) => option.label)
          .join("; ")}. ${rules.changes}`}
        confirmLabel={
          poll.has_voted ? "Confirm vote update" : "Confirm my vote"
        }
        busy={vote.isPending}
        onCancel={() => setConfirm(false)}
        onConfirm={() => vote.mutate()}
      />
    </section>
  );
}

type OrganizerAction = "remind" | "extend" | "close";

function OrganizerTools({ poll, now }: { poll: Poll; now: number }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [action, setAction] = useState<OrganizerAction | null>(null);
  const [reason, setReason] = useState("");
  const [deadline, setDeadline] = useState(utcToAccraInput(poll.closes_at));
  const [confirmAction, setConfirmAction] = useState(false);
  const [publishConfirm, setPublishConfirm] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [requestId, setRequestId] = useState<string | null>(null);
  const recipients = useQuery({
    queryKey: ["polls", "reminder-preview", poll.id],
    queryFn: () =>
      api<{ recipient_count: number }>(
        `/api/v1/polls/${poll.id}/reminders/preview`,
      ),
    enabled: action === "remind",
  });
  const mutation = useMutation({
    mutationFn: ({
      action: intent,
      idempotencyKey,
    }: {
      action: OrganizerAction | "publish" | "duplicate";
      idempotencyKey?: string;
    }) =>
      api<Poll | { recipient_count: number }>(
        `/api/v1/polls/${poll.id}/${intent === "remind" ? "reminders" : intent}`,
        {
          method: "POST",
          ...(intent === "remind"
            ? { headers: { "Idempotency-Key": idempotencyKey ?? "" } }
            : {}),
          ...(intent === "extend"
            ? {
                body: {
                  closes_at: accraInputToUtc(deadline),
                  reason: reason.trim(),
                },
              }
            : intent === "close"
              ? { body: { reason: reason.trim() } }
              : {}),
        },
      ),
    onSuccess: async (result, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["polls"] });
      setConfirmAction(false);
      setPublishConfirm(false);
      setAction(null);
      setReason("");
      setRequestId(null);
      if (variables.action === "duplicate" && "id" in result) {
        toast.success("Poll duplicated as a draft");
        router.push(`/dashboard/polls/${result.id}/edit`);
      } else
        toast.success(
          variables.action === "remind" && "recipient_count" in result
            ? `Reminder sent to ${formatNumber(result.recipient_count)} members who haven’t voted`
            : variables.action === "extend"
              ? "Voting deadline extended"
              : variables.action === "close"
                ? "Poll closed"
                : "Poll published",
        );
    },
    onError: (error) => {
      setConfirmAction(false);
      setPublishConfirm(false);
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not complete this action",
      );
    },
  });
  async function exportCsv() {
    setExporting(true);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/polls/${poll.id}/export`,
        { credentials: "include" },
      );
      if (!response.ok)
        throw new Error("The report could not be exported. Please try again.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `utag-poll-${poll.id}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not export results",
      );
    } finally {
      setExporting(false);
    }
  }
  function prepareAction() {
    if (action === "remind") {
      if (!recipients.data?.recipient_count) return;
      if (!requestId) setRequestId(crypto.randomUUID());
    } else {
      if (reason.trim().length < 3) {
        toast.error(
          "Add a reason using at least three characters so the change is recorded.",
        );
        return;
      }
      if (action === "extend") {
        const closesAt = accraInputToUtc(deadline);
        if (
          !closesAt ||
          Date.parse(closesAt) <=
            Math.max(now, Date.parse(poll.closes_at ?? ""))
        ) {
          toast.error("Choose a deadline later than the current closing time.");
          return;
        }
      }
    }
    setConfirmAction(true);
  }
  const canExtend = poll.status === "open" || poll.status === "scheduled";
  return (
    <section
      data-poll-organizer-panel
      className={cn(
        "workspace-folio min-w-0 rounded-[1.5rem] p-6",
        !action && "poll-organizer-panel",
      )}
    >
      <p className="eyebrow text-coral">Organizer desk</p>
      <h2 className="mt-2 text-lg font-black">Keep the decision moving</h2>
      <div
        aria-label="Poll organizer actions"
        data-poll-organizer-actions
        className="poll-organizer-action-dock mt-5 flex gap-2 sm:flex-wrap"
      >
        {poll.status === "draft" ? (
          <>
            <Button asChild variant="outline" size="sm">
              <Link href={`/dashboard/polls/${poll.id}/edit`}>
                <Edit3 className="size-3.5" /> Edit draft
              </Link>
            </Button>
            <Button
              size="sm"
              variant="gold"
              onClick={() => setPublishConfirm(true)}
              disabled={mutation.isPending}
            >
              <Radio className="size-3.5" /> Publish poll
            </Button>
          </>
        ) : null}
        {poll.status === "open" ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setAction("remind");
              setRequestId(null);
            }}
          >
            <BellRing className="size-3.5" /> Remind non-voters
          </Button>
        ) : null}
        {canExtend ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setAction("extend");
              setReason("");
              setDeadline(utcToAccraInput(poll.closes_at));
            }}
          >
            <Clock3 className="size-3.5" /> Extend deadline
          </Button>
        ) : null}
        {poll.status === "open" ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setAction("close");
              setReason("");
            }}
          >
            <X className="size-3.5" /> Close early
          </Button>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate({ action: "duplicate" })}
        >
          <Copy className="size-3.5" /> Duplicate poll
        </Button>
        {poll.can_export ? (
          <Button
            variant="outline"
            size="sm"
            disabled={exporting}
            onClick={exportCsv}
          >
            {exporting ? (
              <LoaderCircle className="size-3.5 animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}{" "}
            Export CSV
          </Button>
        ) : null}
        {poll.can_view_results ? (
          <Button asChild variant="outline" size="sm">
            <Link href={`/dashboard/polls/${poll.id}/print`}>
              <Printer className="size-3.5" /> Print report
            </Link>
          </Button>
        ) : null}
      </div>
      {action ? (
        <div className="mt-5 rounded-2xl border border-line bg-panel/50 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-bold">
              {action === "remind"
                ? "A gentle nudge to participate"
                : action === "extend"
                  ? "Give members more time"
                  : "Close the voting window"}
            </h3>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Cancel organizer action"
              onClick={() => setAction(null)}
            >
              <X className="size-4" />
            </Button>
          </div>
          {action === "remind" ? (
            <p className="mt-2 text-sm leading-6 text-muted">
              {recipients.isLoading
                ? "Checking who still has a vote to cast…"
                : recipients.error
                  ? "Could not load reminder recipients. Try again."
                  : `${formatNumber(recipients.data?.recipient_count ?? 0)} eligible members have not voted. They will receive one inbox reminder.`}
            </p>
          ) : (
            <div className="mt-4 grid gap-4">
              {action === "extend" ? (
                <label className="grid gap-2 text-xs font-bold">
                  New closing time (Accra / GMT)
                  <input
                    type="datetime-local"
                    value={deadline}
                    onChange={(event) => setDeadline(event.target.value)}
                    className="min-h-12 min-w-0 rounded-xl border border-line bg-paper px-4 text-sm focus:border-coral"
                  />
                </label>
              ) : (
                <p className="text-sm leading-6 text-muted">
                  Voting will stop immediately. Existing ballots remain in the
                  final results.
                </p>
              )}
              <label className="grid gap-2 text-xs font-bold">
                Reason for this change
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  maxLength={1000}
                  className="min-h-24 rounded-xl border border-line bg-paper p-4 text-sm focus:border-coral"
                  placeholder="Explain the decision for the association record."
                />
              </label>
            </div>
          )}
          <Button
            size="sm"
            className="mt-4"
            disabled={
              mutation.isPending ||
              (action === "remind" &&
                (recipients.isFetching || !recipients.data?.recipient_count))
            }
            onClick={prepareAction}
          >
            {action === "remind"
              ? "Review reminder"
              : action === "extend"
                ? "Review extension"
                : "Review early close"}
          </Button>
        </div>
      ) : null}
      <ConfirmDialog
        open={confirmAction}
        title={
          action === "remind"
            ? "Send this reminder?"
            : action === "extend"
              ? "Extend voting?"
              : "Close this poll now?"
        }
        description={
          action === "remind"
            ? `${formatNumber(recipients.data?.recipient_count ?? 0)} eligible members who have not voted will receive an inbox reminder.`
            : action === "extend"
              ? `New closing time: ${formatPollDate(accraInputToUtc(deadline))} GMT. Reason: ${reason}`
              : `Voting will end immediately. Reason: ${reason}`
        }
        confirmLabel={
          action === "remind"
            ? "Send reminder"
            : action === "extend"
              ? "Extend deadline"
              : "Close poll"
        }
        danger={action === "close"}
        busy={mutation.isPending}
        onCancel={() => setConfirmAction(false)}
        onConfirm={() => {
          if (action)
            mutation.mutate({ action, idempotencyKey: requestId ?? undefined });
        }}
      />
      <ConfirmDialog
        open={publishConfirm}
        title="Publish this draft?"
        description="The voting roll, choices, and privacy rules will be fixed. Eligible members will receive a poll invitation."
        confirmLabel="Publish poll"
        busy={mutation.isPending}
        onCancel={() => setPublishConfirm(false)}
        onConfirm={() => mutation.mutate({ action: "publish" })}
      />
    </section>
  );
}

export function PollDetailClient({ pollId }: { pollId: string }) {
  const { state } = useRealtime();
  const poll = useQuery({
    queryKey: ["polls", "detail", pollId],
    queryFn: () => api<Poll>(`/api/v1/polls/${pollId}`),
    refetchInterval: state === "live" ? false : 15_000,
  });
  const result = useQuery({
    queryKey: ["polls", "results", pollId],
    queryFn: () => api<PollResults>(`/api/v1/polls/${pollId}/results`),
    enabled: poll.data?.can_view_results === true,
    refetchInterval:
      poll.data?.status !== "closed" && state !== "live" ? 15_000 : false,
  });
  const now = usePollClock(poll.data?.server_now, poll.dataUpdatedAt);
  usePollBoundaryRefresh(poll.data, poll.dataUpdatedAt);
  if (poll.isLoading) return <PollLoading label="Opening the conversation…" />;
  if (poll.error || !poll.data)
    return <PollError retry={() => poll.refetch()} />;
  const data = poll.data;
  return (
    <div className="grid min-w-0 gap-6">
      <Link
        href="/dashboard/polls"
        className="inline-flex w-fit items-center gap-2 text-xs font-bold text-muted"
      >
        <ArrowLeft className="size-4" /> Back to polls
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-3xl">
          <PollStatusBadge status={data.status} />
          <h1 className="display-type mt-4 text-3xl leading-tight sm:text-4xl">
            {data.title}
          </h1>
        </div>
        <div className="rounded-2xl border border-gold/25 bg-gold/6 px-5 py-4">
          <p className="flex items-center gap-2 text-xs font-bold">
            <Clock3 className="size-4 text-gold" />
            {data.status === "scheduled"
              ? "Voting opens in"
              : data.status === "closed"
                ? "Voting complete"
                : "Voting window"}
          </p>
          <p className="mt-2 text-base font-black">
            {data.status === "draft"
              ? "Draft · not published"
              : data.status === "closed"
                ? "Poll closed"
                : pollCountdown(
                    data.status === "scheduled"
                      ? data.opens_at
                      : data.closes_at,
                    now,
                  )}
          </p>
        </div>
      </header>
      <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <div className="grid min-w-0 gap-5">
          <PollBallot
            poll={data}
            key={`${data.id}:${data.my_vote?.join(",") ?? "unvoted"}`}
          />
          <section className="rounded-2xl border border-line p-5">
            <h3 className="flex items-center gap-2 text-xs font-bold">
              <CalendarDays className="size-4 text-coral" /> The voting window
            </h3>
            <dl className="mt-4 grid gap-4 text-xs sm:grid-cols-2">
              <div>
                <dt className="text-muted">Opens · Accra (GMT)</dt>
                <dd className="mt-1 font-semibold">
                  {formatPollDate(data.opens_at)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Closes · Accra (GMT)</dt>
                <dd className="mt-1 font-semibold">
                  {data.closes_at
                    ? formatPollDate(
                        data.status === "closed"
                          ? (data.closed_at ?? data.closes_at)
                          : data.closes_at,
                      )
                    : "Not set"}
                </dd>
              </div>
            </dl>
            <p className="mt-4 flex items-center gap-2 text-xs text-muted">
              <Users className="size-3.5" /> {formatNumber(data.eligible_count)}{" "}
              eligible members ·{" "}
              {data.published_at
                ? "Voting roll fixed at publication"
                : "Audience preview"}
            </p>
          </section>
        </div>
        <div className="grid min-w-0 gap-5">
          {data.can_view_results ? (
            result.isLoading ? (
              <PollLoading label="Counting the participation…" />
            ) : result.error || !result.data ? (
              <PollError
                message="Results could not be refreshed. Your ballot remains recorded."
                retry={() => result.refetch()}
              />
            ) : (
              <PollResultsPanel poll={data} results={result.data} />
            )
          ) : (
            <section className="workspace-folio rounded-[1.5rem] p-7 sm:p-9">
              <span className="grid size-12 place-items-center rounded-2xl bg-gold/10 text-gold">
                <EyeOff className="size-5" />
              </span>
              <p className="eyebrow mt-6 text-coral">A fair space to decide</p>
              <h2 className="display-type mt-3 text-2xl">
                {data.results_visibility === "after_vote"
                  ? "Results after your vote"
                  : "Results when voting closes"}
              </h2>
              <p className="mt-4 text-sm leading-7 text-muted">
                {data.results_visibility === "after_vote"
                  ? "Cast your ballot to follow the aggregate results."
                  : `Your choice matters on its own. Aggregate member results will be available after the voting window closes${data.closes_at ? ` on ${formatPollDate(data.closes_at)} GMT` : ""}.`}
              </p>
              <div className="workspace-rule mt-6" />
              <p className="mt-5 flex items-start gap-2 text-xs leading-6 text-muted">
                <ShieldCheck className="mt-1 size-4 shrink-0 text-gold" />
                {pollRules(data).privacy}
              </p>
            </section>
          )}
          {data.can_manage ? (
            <OrganizerTools poll={data} now={now} />
          ) : !data.can_view_results ? (
            <p className="flex items-start gap-2 px-2 text-xs leading-6 text-muted">
              <FileText className="mt-1 size-4 shrink-0" />
              This poll’s rules are shown before you submit, so you know how
              your vote will be used.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
