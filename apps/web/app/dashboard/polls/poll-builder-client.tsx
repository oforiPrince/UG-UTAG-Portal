"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Eye,
  FileText,
  Info,
  ListChecks,
  LoaderCircle,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDeferredValue, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import {
  accraInputToUtc,
  audienceKey,
  formatPollDate,
  INDUSTRIAL_ACTION_TEMPLATE,
  pollAudienceLabels,
  pollDraftFromView,
  pollRules,
  utcToAccraInput,
  type Poll,
  type PollAudience,
  type PollAudienceOption,
  type PollAudienceType,
  type PollInput,
  type PollPage,
} from "@/lib/polls";
import { cn, formatNumber } from "@/lib/utils";

import { PollError, PollLoading } from "./poll-ui";

const inputClass =
  "min-h-12 w-full rounded-xl border border-line bg-panel/65 px-4 text-sm outline-none transition focus:border-coral";
const steps = [
  {
    title: "The question",
    note: "Give members a clear choice",
    icon: ListChecks,
  },
  { title: "The audience", note: "Decide who has a voice", icon: Users },
  {
    title: "Time & trust",
    note: "Set the window and rules",
    icon: ShieldCheck,
  },
  {
    title: "Review & launch",
    note: "See it through a member’s eyes",
    icon: Eye,
  },
];
const newPoll: PollInput = {
  title: "",
  question: "",
  description: "",
  kind: "single",
  privacy: "confidential",
  results_visibility: "after_close",
  allow_vote_changes: false,
  max_choices: 1,
  opens_at: null,
  closes_at: null,
  audiences: [{ type: "all_members" }],
  options: ["", ""],
};

async function resolveAudienceLabels(audiences: PollAudience[]) {
  const labels: Record<string, string> = {};
  const types = [...new Set(audiences.map((audience) => audience.type))].filter(
    (type) => type !== "all_members",
  );
  await Promise.all(
    types.map(async (type) => {
      const wanted = new Set(
        audiences.filter((audience) => audience.type === type).map(audienceKey),
      );
      let page = 1;
      while (wanted.size) {
        const result = await api<PollPage<PollAudienceOption>>(
          `/api/v1/polls/audiences?${new URLSearchParams({ type, page: String(page), page_size: "100" })}`,
        );
        for (const item of result.items) {
          const key = audienceKey(item);
          if (!wanted.has(key)) continue;
          labels[key] = item.label;
          wanted.delete(key);
        }
        if (page >= result.pages) break;
        page += 1;
      }
    }),
  );
  return labels;
}

function AudiencePicker({
  value,
  onChange,
  labels,
  setLabel,
}: {
  value: PollAudience[];
  onChange: (value: PollAudience[]) => void;
  labels: Record<string, string>;
  setLabel: (key: string, label: string) => void;
}) {
  const [type, setType] = useState<PollAudienceType>("college");
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const [page, setPage] = useState(1);
  const all = value.some((rule) => rule.type === "all_members");
  const lookup = useQuery({
    queryKey: ["polls", "audiences", type, q, page],
    queryFn: () =>
      api<PollPage<PollAudienceOption>>(
        `/api/v1/polls/audiences?${new URLSearchParams({ type, q, page: String(page), page_size: "15" })}`,
      ),
    enabled: !all,
  });
  const preview = useQuery({
    queryKey: ["polls", "audience-preview", value],
    queryFn: () =>
      api<{ eligible_count: number }>("/api/v1/polls/audience-preview", {
        method: "POST",
        body: { audiences: value },
      }),
    enabled: Boolean(value.length),
  });
  function toggle(item: PollAudienceOption) {
    const key = audienceKey(item);
    setLabel(key, item.label);
    onChange(
      value.some((rule) => audienceKey(rule) === key)
        ? value.filter((rule) => audienceKey(rule) !== key)
        : [...value, { type: item.type, value: item.value }],
    );
  }
  return (
    <div className="grid gap-6">
      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          aria-pressed={all}
          onClick={() => onChange([{ type: "all_members" }])}
          className={cn(
            "rounded-2xl border p-5 text-left",
            all ? "border-coral bg-coral/5" : "border-line bg-panel/40",
          )}
        >
          <Users className="size-5 text-coral" />
          <b className="mt-3 block text-sm">All active members</b>
          <span className="mt-2 block text-xs leading-5 text-muted">
            Bring the entire association into the decision.
          </span>
        </button>
        <button
          type="button"
          aria-pressed={!all}
          onClick={() => {
            if (all) onChange([]);
          }}
          className={cn(
            "rounded-2xl border p-5 text-left",
            !all ? "border-coral bg-coral/5" : "border-line bg-panel/40",
          )}
        >
          <ListChecks className="size-5 text-coral" />
          <b className="mt-3 block text-sm">Targeted audience</b>
          <span className="mt-2 block text-xs leading-5 text-muted">
            Combine organization units, roles, groups, or members.
          </span>
        </button>
      </div>
      {!all ? (
        <>
          <div className="grid gap-3 sm:grid-cols-[12rem_1fr]">
            <label className="grid gap-2 text-xs font-bold">
              Find by
              <select
                aria-label="Audience type"
                className={inputClass}
                value={type}
                onChange={(event) => {
                  setType(event.target.value as PollAudienceType);
                  setPage(1);
                  setSearch("");
                }}
              >
                {(Object.keys(pollAudienceLabels) as PollAudienceType[])
                  .filter((key) => key !== "all_members")
                  .map((key) => (
                    <option value={key} key={key}>
                      {pollAudienceLabels[key]}
                    </option>
                  ))}
              </select>
            </label>
            <label className="grid gap-2 text-xs font-bold">
              Search
              <span className="flex min-h-12 items-center gap-3 rounded-xl border border-line bg-panel/65 px-4">
                <Search className="size-4 text-muted" />
                <input
                  aria-label="Search audience"
                  className="min-w-0 flex-1 bg-transparent text-sm font-normal outline-none"
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setPage(1);
                  }}
                  placeholder={`Search ${pollAudienceLabels[type].toLowerCase()}…`}
                />
              </span>
            </label>
          </div>
          {value.length ? (
            <div
              className="flex flex-wrap gap-2"
              aria-label="Selected audience"
            >
              {value.map((rule) => (
                <button
                  key={audienceKey(rule)}
                  type="button"
                  onClick={() =>
                    onChange(
                      value.filter(
                        (item) => audienceKey(item) !== audienceKey(rule),
                      ),
                    )
                  }
                  aria-label={`Remove ${labels[audienceKey(rule)] ?? pollAudienceLabels[rule.type]}`}
                  className="inline-flex items-center gap-2 rounded-full bg-coral/8 px-3 py-2 text-xs font-bold text-coral"
                >
                  {labels[audienceKey(rule)] ??
                    `${pollAudienceLabels[rule.type]} · unavailable selection`}
                  <X className="size-3" />
                </button>
              ))}
            </div>
          ) : null}
          <div className="max-h-72 divide-y divide-line overflow-y-auto rounded-2xl border border-line">
            {lookup.isLoading ? (
              <p className="p-6 text-center text-sm text-muted">
                Finding audiences…
              </p>
            ) : lookup.error ? (
              <p className="p-6 text-sm text-muted">
                Could not load audiences.{" "}
                <button
                  type="button"
                  className="font-bold text-coral"
                  onClick={() => lookup.refetch()}
                >
                  Try again
                </button>
              </p>
            ) : !lookup.data?.items.length ? (
              <p className="p-6 text-center text-sm text-muted">
                No eligible audiences match this search.
              </p>
            ) : (
              lookup.data.items.map((item) => {
                const selected = value.some(
                  (rule) => audienceKey(rule) === audienceKey(item),
                );
                return (
                  <label
                    key={audienceKey(item)}
                    className="flex min-h-12 cursor-pointer items-center gap-3 px-4 py-3 text-sm hover:bg-panel"
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggle(item)}
                      className="size-4 accent-[var(--coral)]"
                    />
                    <span className="min-w-0">{item.label}</span>
                  </label>
                );
              })
            )}
          </div>
          {lookup.data && lookup.data.pages > 1 ? (
            <div className="flex items-center justify-end gap-3">
              <Button
                size="sm"
                variant="outline"
                aria-label="Previous audiences"
                disabled={page === 1}
                onClick={() => setPage((value) => value - 1)}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <span className="text-xs text-muted">
                {page} of {lookup.data.pages}
              </span>
              <Button
                size="sm"
                variant="outline"
                aria-label="Next audiences"
                disabled={page >= lookup.data.pages}
                onClick={() => setPage((value) => value + 1)}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
      <div className="rounded-2xl bg-[#10213b] p-5 text-white">
        <p className="text-[.65rem] font-bold tracking-wider text-white/55 uppercase">
          Audience preview
        </p>
        <p className="mt-2 flex items-baseline gap-2">
          <b className="display-type text-3xl">
            {preview.isFetching
              ? "…"
              : preview.error
                ? "—"
                : formatNumber(preview.data?.eligible_count ?? 0)}
          </b>
          <span className="text-xs text-white/65">eligible active members</span>
        </p>
        <p className="mt-3 text-xs leading-5 text-white/60">
          Members in any selected audience are included once. The voting roll is
          fixed when you publish.
        </p>
        {preview.error ? (
          <button
            type="button"
            onClick={() => preview.refetch()}
            className="mt-2 text-xs font-bold text-gold"
          >
            Retry audience preview
          </button>
        ) : null}
      </div>
    </div>
  );
}

function PollBuilderForm({
  initial,
  pollId,
  version,
}: {
  initial: PollInput;
  pollId?: string;
  version?: number;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(initial);
  const [immediate, setImmediate] = useState(initial.opens_at === null);
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<string[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [confirmPublish, setConfirmPublish] = useState(false);
  const savedAudienceLabels = useQuery({
    queryKey: ["polls", "saved-audience-labels", pollId],
    queryFn: () => resolveAudienceLabels(initial.audiences),
    enabled:
      Boolean(pollId) &&
      !initial.audiences.some((rule) => rule.type === "all_members"),
    staleTime: 300_000,
  });
  const savedDraft = useRef<{ id: string; version: number } | null>(
    pollId && version ? { id: pollId, version } : null,
  );
  const preview = useQuery({
    queryKey: ["polls", "audience-preview", draft.audiences],
    queryFn: () =>
      api<{ eligible_count: number }>("/api/v1/polls/audience-preview", {
        method: "POST",
        body: { audiences: draft.audiences },
      }),
    enabled: Boolean(draft.audiences.length),
  });
  const save = useMutation({
    mutationFn: async (publish: boolean) => {
      const body = {
        ...draft,
        title: draft.title.trim(),
        question: draft.question.trim(),
        description: draft.description.trim(),
        options: draft.options.map((option) => option.trim()),
        max_choices: draft.kind === "single" ? 1 : draft.max_choices,
      };
      const existing = savedDraft.current;
      const saved = await api<Poll>(
        existing ? `/api/v1/polls/${existing.id}` : "/api/v1/polls",
        {
          method: existing ? "PATCH" : "POST",
          body,
          ...(existing
            ? { headers: { "If-Match": `"${existing.version}"` } }
            : {}),
        },
      );
      savedDraft.current = { id: saved.id, version: saved.version };
      if (!publish) return saved;
      return api<Poll>(`/api/v1/polls/${saved.id}/publish`, { method: "POST" });
    },
    onSuccess: async (poll, publish) => {
      await queryClient.invalidateQueries({ queryKey: ["polls"] });
      toast.success(
        publish
          ? poll.status === "scheduled"
            ? "Poll scheduled. Your audience is ready."
            : "Poll published. Voting is open."
          : "Poll draft saved",
      );
      router.push(`/dashboard/polls/${poll.id}`);
    },
    onError: (error, publish) => {
      setConfirmPublish(false);
      toast.error(
        `${publish && savedDraft.current ? "Your draft is saved. " : ""}${error instanceof Error ? error.message : "Could not save poll"}`,
      );
    },
  });
  function update<K extends keyof PollInput>(key: K, value: PollInput[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  function validate(part: number, publishing = false) {
    const issues: string[] = [];
    if (part === 0 || publishing) {
      if (draft.title.trim().length < 3)
        issues.push("Give this poll a title using at least three characters.");
      if (draft.question.trim().length < 3)
        issues.push("Write a question using at least three characters.");
      if (
        draft.options.length < 2 ||
        draft.options.some((option) => !option.trim())
      )
        issues.push("Add at least two complete answer choices.");
      if (
        new Set(draft.options.map((option) => option.trim().toLowerCase()))
          .size !== draft.options.length
      )
        issues.push("Each answer choice must be different.");
      if (
        draft.kind === "multiple" &&
        (!draft.max_choices ||
          draft.max_choices < 1 ||
          draft.max_choices > draft.options.length)
      )
        issues.push(
          "Choose a selection limit between one and the number of answers.",
        );
    }
    if ((part === 1 || publishing) && !draft.audiences.length)
      issues.push("Select at least one audience.");
    if (part === 2 || publishing) {
      if (!immediate && !draft.opens_at)
        issues.push("Set an opening time, or select Open immediately.");
      if (publishing && !draft.closes_at)
        issues.push("Set a closing time before publishing.");
      if (draft.closes_at && Date.parse(draft.closes_at) <= Date.now())
        issues.push("The closing time must be in the future.");
      if (
        draft.closes_at &&
        draft.opens_at &&
        Date.parse(draft.closes_at) <= Date.parse(draft.opens_at)
      )
        issues.push("The poll must close after its opening time.");
      if (draft.opens_at && Date.parse(draft.opens_at) <= Date.now())
        issues.push(
          "Choose a future opening time, or select Open immediately.",
        );
    }
    if (
      publishing &&
      (preview.isFetching || preview.error || !preview.data?.eligible_count)
    )
      issues.push(
        "Confirm an audience with at least one eligible member before publishing.",
      );
    setErrors(issues);
    return !issues.length;
  }
  const rules = pollRules(draft);
  const busy = save.isPending;
  return (
    <div className="mx-auto grid max-w-6xl gap-6">
      <Link
        href={pollId ? `/dashboard/polls/${pollId}` : "/dashboard/polls"}
        className="inline-flex w-fit items-center gap-2 text-xs font-bold text-muted"
      >
        <ArrowLeft className="size-4" /> Back to polls
      </Link>
      <header>
        <p className="eyebrow text-coral">A decision worth making together</p>
        <h1 className="display-type mt-3 text-3xl sm:text-4xl">
          {pollId ? "Refine your poll" : "Create a poll"}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          A clear question. The right people. A trusted voting window.
        </p>
      </header>
      <ol
        className="grid grid-cols-2 gap-3 lg:grid-cols-4"
        aria-label="Poll creation steps"
      >
        {steps.map((item, index) => {
          const Icon = item.icon;
          return (
            <li
              key={item.title}
              className={cn(
                "rounded-2xl border px-4 py-4",
                index === step
                  ? "border-coral/35 bg-coral/5"
                  : "border-line bg-paper/50",
              )}
              aria-current={index === step ? "step" : undefined}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "grid size-6 place-items-center rounded-full text-[.65rem] font-bold",
                    index === step
                      ? "bg-ink text-paper"
                      : "bg-ink/5 text-muted",
                  )}
                >
                  {index < step ? <Check className="size-3.5" /> : index + 1}
                </span>
                <Icon className="size-4 text-muted" />
                <b className="text-xs">{item.title}</b>
              </div>
              <p className="mt-2 hidden text-[.65rem] text-muted sm:block">
                {item.note}
              </p>
            </li>
          );
        })}
      </ol>
      <form
        className="workspace-folio overflow-hidden rounded-[1.6rem]"
        onSubmit={(event) => {
          event.preventDefault();
          if (step < 3 && validate(step)) setStep((value) => value + 1);
          else if (step === 3 && validate(3, true)) setConfirmPublish(true);
        }}
      >
        <div className="p-6 sm:p-9">
          {errors.length ? (
            <div
              role="alert"
              className="mb-6 rounded-2xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-700 dark:text-red-300"
            >
              <p className="font-bold">A few details need your attention</p>
              <ul className="mt-2 list-disc pl-5">
                {errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {step === 0 ? (
            <div className="grid gap-6">
              {!pollId ? (
                <button
                  type="button"
                  onClick={() => {
                    setDraft((current) => ({
                      ...current,
                      ...INDUSTRIAL_ACTION_TEMPLATE,
                      kind: "single",
                      max_choices: 1,
                    }));
                    setErrors([]);
                  }}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gold/25 bg-gold/6 p-5 text-left"
                >
                  <span>
                    <b className="flex items-center gap-2 text-sm">
                      <Sparkles className="size-4 text-gold" /> Start with the
                      industrial action poll
                    </b>
                    <span className="mt-2 block text-xs leading-5 text-muted">
                      Your question, with the exact YES and NO choices already
                      prepared.
                    </span>
                  </span>
                  <ArrowRight className="size-4 text-gold" />
                </button>
              ) : null}
              <label className="grid gap-2 text-xs font-bold">
                Poll title{" "}
                <input
                  className={`${inputClass} min-h-15 text-base font-semibold`}
                  value={draft.title}
                  onChange={(event) => update("title", event.target.value)}
                  maxLength={250}
                  placeholder="A short title members will recognize"
                />
              </label>
              <label className="grid gap-2 text-xs font-bold">
                Poll question{" "}
                <textarea
                  className={`${inputClass} min-h-28 py-4 text-base leading-7`}
                  value={draft.question}
                  onChange={(event) => update("question", event.target.value)}
                  maxLength={3000}
                  placeholder="What decision are we making together?"
                />
              </label>
              <label className="grid gap-2 text-xs font-bold">
                Context{" "}
                <span className="font-normal text-muted">
                  Optional · Plain text
                </span>
                <textarea
                  className={`${inputClass} min-h-24 py-4 leading-6`}
                  value={draft.description}
                  onChange={(event) =>
                    update("description", event.target.value)
                  }
                  maxLength={10000}
                  placeholder="Give members the background they need to make an informed choice."
                />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="grid gap-2 text-xs font-bold">
                  Voting format
                  <select
                    className={inputClass}
                    value={draft.kind}
                    onChange={(event) => {
                      const kind = event.target.value as Poll["kind"];
                      setDraft((current) => ({
                        ...current,
                        kind,
                        max_choices:
                          kind === "multiple" ? current.options.length : 1,
                      }));
                    }}
                  >
                    <option value="single">Choose one answer</option>
                    <option value="multiple">Choose several answers</option>
                  </select>
                </label>
                {draft.kind === "multiple" ? (
                  <label className="grid gap-2 text-xs font-bold">
                    Maximum selections
                    <input
                      className={inputClass}
                      type="number"
                      min={1}
                      max={draft.options.length}
                      value={draft.max_choices}
                      onChange={(event) =>
                        update("max_choices", Number(event.target.value))
                      }
                    />
                  </label>
                ) : null}
              </div>
              <fieldset>
                <legend className="text-xs font-bold">Answer choices</legend>
                <div className="mt-3 grid gap-3">
                  {draft.options.map((option, index) => (
                    <div className="flex items-start gap-2" key={index}>
                      <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-ink/5 text-xs font-bold text-muted">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <label className="min-w-0 flex-1">
                        <span className="sr-only">
                          Answer choice {index + 1}
                        </span>
                        <input
                          className={inputClass}
                          value={option}
                          maxLength={500}
                          onChange={(event) =>
                            update(
                              "options",
                              draft.options.map((value, position) =>
                                position === index ? event.target.value : value,
                              ),
                            )
                          }
                          placeholder={`Answer choice ${index + 1}`}
                        />
                      </label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        disabled={draft.options.length <= 2}
                        aria-label={`Remove answer ${index + 1}`}
                        onClick={() =>
                          update(
                            "options",
                            draft.options.filter(
                              (_, position) => position !== index,
                            ),
                          )
                        }
                      >
                        <Trash2 className="size-4 text-muted" />
                      </Button>
                    </div>
                  ))}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  disabled={draft.options.length >= 20}
                  onClick={() => update("options", [...draft.options, ""])}
                >
                  <Plus className="size-3.5" /> Add answer choice
                </Button>
              </fieldset>
            </div>
          ) : step === 1 ? (
            <AudiencePicker
              value={draft.audiences}
              onChange={(value) => update("audiences", value)}
              labels={{ ...savedAudienceLabels.data, ...labels }}
              setLabel={(key, label) =>
                setLabels((current) => ({ ...current, [key]: label }))
              }
            />
          ) : step === 2 ? (
            <div className="grid gap-7">
              <section>
                <h2 className="flex items-center gap-2 text-lg font-black">
                  <Clock3 className="size-5 text-coral" /> Voting window
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted">
                  All times below are in Africa/Accra (GMT / UTC+0), wherever
                  you are.
                </p>
                <label className="mt-4 flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="size-4 accent-[var(--coral)]"
                    checked={immediate}
                    onChange={(event) => {
                      setImmediate(event.target.checked);
                      update(
                        "opens_at",
                        event.target.checked
                          ? null
                          : new Date(Date.now() + 3_600_000).toISOString(),
                      );
                    }}
                  />{" "}
                  Open immediately when published
                </label>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  {!immediate ? (
                    <label className="grid gap-2 text-xs font-bold">
                      Opening time (GMT)
                      <input
                        className={inputClass}
                        type="datetime-local"
                        value={utcToAccraInput(draft.opens_at)}
                        onChange={(event) =>
                          update(
                            "opens_at",
                            accraInputToUtc(event.target.value),
                          )
                        }
                      />
                    </label>
                  ) : (
                    <div className="rounded-xl bg-panel px-4 py-3">
                      <p className="text-xs font-bold">Opening time</p>
                      <p className="mt-2 text-sm text-muted">
                        Immediately on publication
                      </p>
                    </div>
                  )}
                  <label className="grid gap-2 text-xs font-bold">
                    Closing time (GMT)
                    <input
                      className={inputClass}
                      type="datetime-local"
                      value={utcToAccraInput(draft.closes_at)}
                      onChange={(event) =>
                        update("closes_at", accraInputToUtc(event.target.value))
                      }
                    />
                  </label>
                </div>
                <p className="mt-3 text-xs text-muted">
                  Voting opens and closes automatically. Organizers can extend
                  or close an open poll with a recorded reason.
                </p>
              </section>
              <div className="workspace-rule" />
              <section>
                <h2 className="flex items-center gap-2 text-lg font-black">
                  <ShieldCheck className="size-5 text-coral" /> Trust &
                  visibility
                </h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="grid gap-2 text-xs font-bold">
                    Ballot privacy
                    <select
                      className={inputClass}
                      value={draft.privacy}
                      onChange={(event) =>
                        update("privacy", event.target.value as Poll["privacy"])
                      }
                    >
                      <option value="confidential">
                        Confidential · aggregate choices only
                      </option>
                      <option value="named">
                        Named · organizers can see choices
                      </option>
                    </select>
                  </label>
                  <label className="grid gap-2 text-xs font-bold">
                    Member result visibility
                    <select
                      className={inputClass}
                      value={draft.results_visibility}
                      onChange={(event) =>
                        update(
                          "results_visibility",
                          event.target.value as Poll["results_visibility"],
                        )
                      }
                    >
                      <option value="live">Live throughout voting</option>
                      <option value="after_vote">After a member votes</option>
                      <option value="after_close">After voting closes</option>
                    </select>
                  </label>
                </div>
                <label className="mt-5 flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="size-4 accent-[var(--coral)]"
                    checked={draft.allow_vote_changes}
                    onChange={(event) =>
                      update("allow_vote_changes", event.target.checked)
                    }
                  />{" "}
                  Allow members to update their vote until closing
                </label>
                <div className="mt-5 grid gap-2 rounded-2xl bg-panel p-5 text-xs leading-5 text-muted">
                  <p>{rules.privacy}</p>
                  <p>{rules.results}</p>
                  <p>{rules.changes}</p>
                  <p className="font-bold text-ink">
                    Authorized result viewers can follow aggregate statistics
                    live. Privacy, choices, and audience are locked when
                    published.
                  </p>
                </div>
              </section>
            </div>
          ) : (
            <div className="grid gap-7 lg:grid-cols-[1.35fr_1fr]">
              <section className="rounded-2xl border border-line p-6">
                <p className="eyebrow text-coral">Member ballot preview</p>
                <h2 className="display-type mt-4 text-2xl">{draft.title}</h2>
                <p className="mt-5 text-base font-semibold leading-7">
                  {draft.question}
                </p>
                {draft.description ? (
                  <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted">
                    {draft.description}
                  </p>
                ) : null}
                <div className="mt-6 grid gap-3">
                  {draft.options.map((option, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-3 rounded-xl border border-line px-4 py-4 text-sm"
                    >
                      <span
                        className={cn(
                          "size-4 shrink-0 border border-muted/40",
                          draft.kind === "single" ? "rounded-full" : "rounded",
                        )}
                      />
                      {option}
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-xs leading-5 text-muted">
                  {draft.kind === "single"
                    ? "Choose one answer."
                    : `Choose up to ${draft.max_choices} answers.`}
                </p>
              </section>
              <aside className="grid content-start gap-5">
                <div className="rounded-2xl bg-[#10213b] p-6 text-white">
                  <p className="eyebrow text-gold">Ready for your audience</p>
                  <p className="display-type mt-4 text-4xl">
                    {formatNumber(preview.data?.eligible_count ?? 0)}
                  </p>
                  <p className="mt-2 text-xs text-white/65">
                    eligible active members
                  </p>
                  <p className="mt-4 text-xs leading-6 text-white/65">
                    {draft.audiences.some((rule) => rule.type === "all_members")
                      ? "All active association members"
                      : `${draft.audiences.length} selected audiences · overlapping members included once`}
                  </p>
                </div>
                <dl className="grid gap-4 rounded-2xl bg-panel p-5 text-sm">
                  <div>
                    <dt className="text-xs text-muted">Opens</dt>
                    <dd className="mt-1 font-bold">
                      {formatPollDate(draft.opens_at)}
                      {draft.opens_at ? " GMT" : ""}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Closes</dt>
                    <dd className="mt-1 font-bold">
                      {draft.closes_at
                        ? `${formatPollDate(draft.closes_at)} GMT`
                        : "Set a closing time to publish"}
                    </dd>
                  </div>
                </dl>
                <div className="space-y-3 text-xs leading-5 text-muted">
                  <p>{rules.privacy}</p>
                  <p>{rules.results}</p>
                  <p>{rules.changes}</p>
                </div>
                <p className="flex items-start gap-2 rounded-xl border border-gold/25 bg-gold/5 p-4 text-xs leading-5">
                  <Info className="mt-0.5 size-4 shrink-0 text-gold" />{" "}
                  Publishing fixes the voting roll and sends an inbox invitation
                  when voting opens.
                </p>
              </aside>
            </div>
          )}
        </div>
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-panel/40 px-6 py-5 sm:px-9">
          <Button
            type="button"
            variant="ghost"
            disabled={step === 0 || busy}
            onClick={() => {
              setStep((value) => value - 1);
              setErrors([]);
            }}
          >
            <ArrowLeft className="size-4" /> Back
          </Button>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => {
                if (validate(0)) save.mutate(false);
              }}
            >
              <FileText className="size-4" /> Save draft
            </Button>
            <Button
              type="submit"
              variant={step === 3 ? "gold" : "primary"}
              disabled={busy}
            >
              {busy ? <LoaderCircle className="size-4 animate-spin" /> : null}
              {step === 3 ? "Publish poll" : "Continue"}
              {step < 3 ? <ArrowRight className="size-4" /> : null}
            </Button>
          </div>
        </footer>
      </form>
      <ConfirmDialog
        open={confirmPublish}
        title={draft.opens_at ? "Schedule this poll?" : "Open voting now?"}
        description={`Publish “${draft.title}” for ${formatNumber(preview.data?.eligible_count ?? 0)} eligible members. The question, choices, audience, and privacy rules will be fixed. Eligible members will receive a poll invitation when voting opens.`}
        confirmLabel={
          draft.opens_at ? "Schedule poll" : "Publish & open voting"
        }
        busy={busy}
        onCancel={() => setConfirmPublish(false)}
        onConfirm={() => save.mutate(true)}
      />
    </div>
  );
}

export function PollBuilderClient({ pollId }: { pollId?: string }) {
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<{ permissions: string[] }>("/api/v1/auth/me"),
    staleTime: 60_000,
  });
  const poll = useQuery({
    queryKey: ["polls", "detail", pollId],
    queryFn: () => api<Poll>(`/api/v1/polls/${pollId}`),
    enabled: Boolean(pollId),
  });
  if (user.isLoading || (pollId && poll.isLoading))
    return <PollLoading label="Preparing your poll…" />;
  if (pollId && poll.error) return <PollError retry={() => poll.refetch()} />;
  if (
    !user.data?.permissions.includes("polls.manage") ||
    (poll.data && (!poll.data.can_manage || poll.data.status !== "draft"))
  )
    return (
      <div className="workspace-folio rounded-3xl p-10 text-center">
        <h1 className="display-type text-2xl">This poll cannot be edited</h1>
        <p className="mt-3 text-sm text-muted">
          Draft polls can be edited by authorized organizers. Published
          questions and rules are fixed.
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard/polls">Return to polls</Link>
        </Button>
      </div>
    );
  return (
    <PollBuilderForm
      key={pollId ?? "new"}
      initial={poll.data ? pollDraftFromView(poll.data) : newPoll}
      pollId={pollId}
      version={poll.data?.version}
    />
  );
}
