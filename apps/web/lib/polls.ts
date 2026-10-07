export type PollStatus = "draft" | "scheduled" | "open" | "closed";
export type PollAudienceType =
  | "all_members"
  | "college"
  | "school"
  | "department"
  | "role"
  | "chat_group"
  | "member";
export type PollAudience = { type: PollAudienceType; value?: string };
export type PollAudienceOption = PollAudience & { label: string };
export type PollOption = { id: string; label: string; position: number };
export type Poll = {
  id: string;
  title: string;
  question: string;
  description: string;
  kind: "single" | "multiple";
  privacy: "confidential" | "named";
  results_visibility: "live" | "after_vote" | "after_close";
  allow_vote_changes: boolean;
  max_choices: number;
  opens_at: string | null;
  closes_at: string | null;
  closed_at?: string | null;
  audiences: PollAudience[];
  options: PollOption[];
  status: PollStatus;
  published_at: string | null;
  eligible_count: number;
  has_voted: boolean;
  my_vote: string[] | null;
  can_vote: boolean;
  can_manage: boolean;
  can_view_results: boolean;
  can_export: boolean;
  created_at: string;
  version: number;
  server_now: string;
};
export type PollInput = Pick<
  Poll,
  | "title"
  | "question"
  | "description"
  | "kind"
  | "privacy"
  | "results_visibility"
  | "allow_vote_changes"
  | "max_choices"
  | "opens_at"
  | "closes_at"
  | "audiences"
> & { options: string[] };
export type PollResults = {
  response_count: number;
  eligible_count: number;
  turnout_percent: number;
  options: { id: string; label: string; votes: number; percent: number }[];
  timeline: { at: string; responses: number }[];
  generated_at: string;
  named_voters: { member_name: string; option_labels: string[] }[] | null;
};
export type PollPage<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export const pollAudienceLabels: Record<PollAudienceType, string> = {
  all_members: "All active members",
  college: "Colleges",
  school: "Schools",
  department: "Departments",
  role: "Portal roles",
  chat_group: "Chat groups",
  member: "Selected members",
};

export const INDUSTRIAL_ACTION_TEMPLATE = {
  title: "Industrial action: have your say",
  question:
    "Do you support that UTAG-UG embarks on an indefinite industrial action which will only be called off upon full payment of both Promotion Arrears and BRA?",
  options: [
    "YES, I support the industrial action",
    "NO, I do not support the industrial action",
  ],
};

export function audienceKey(audience: PollAudience) {
  return `${audience.type}:${audience.value ?? ""}`;
}

/** Accra is GMT year-round. Explicit Z avoids interpreting device-local time. */
export function accraInputToUtc(value: string): string | null {
  if (!value) return null;
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null;
  const date = new Date(`${value}:00Z`);
  if (!Number.isFinite(date.getTime())) return null;
  return date.toISOString().slice(0, 16) === value ? date.toISOString() : null;
}

export function utcToAccraInput(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 16) : "";
}

export function formatPollDate(value: string | null) {
  if (!value) return "Immediately";
  return new Intl.DateTimeFormat("en-GH", {
    timeZone: "Africa/Accra",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function pollCountdown(value: string | null, now: number) {
  if (!value) return "No deadline set";
  const seconds = Math.max(0, Math.ceil((Date.parse(value) - now) / 1_000));
  if (!seconds) return "Time window ended";
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  if (days) return `${days}d ${hours}h remaining`;
  if (hours) return `${hours}h ${minutes}m remaining`;
  if (minutes) return `${minutes}m ${seconds % 60}s remaining`;
  return `${seconds}s remaining`;
}

export function togglePollChoice(
  current: string[],
  optionId: string,
  kind: Poll["kind"],
  maxChoices: number | null,
) {
  if (kind === "single") return [optionId];
  if (current.includes(optionId))
    return current.filter((id) => id !== optionId);
  if (maxChoices && current.length >= maxChoices) return current;
  return [...current, optionId];
}

export function pollRules(
  poll: Pick<Poll, "privacy" | "results_visibility" | "allow_vote_changes">,
) {
  return {
    privacy:
      poll.privacy === "named"
        ? "Named ballot: authorized organizers can see your name and choices."
        : "Confidential ballot: your choices are shown only in aggregate results.",
    results:
      poll.results_visibility === "live"
        ? "Eligible members can see results while voting is open."
        : poll.results_visibility === "after_vote"
          ? "Results become visible after you vote."
          : "Member results become visible when the poll closes.",
    changes: poll.allow_vote_changes
      ? "You can change your vote until voting closes."
      : "Your vote is final after submission.",
  };
}

export function pollDraftFromView(poll: Poll): PollInput {
  return {
    title: poll.title,
    question: poll.question,
    description: poll.description,
    kind: poll.kind,
    privacy: poll.privacy,
    results_visibility: poll.results_visibility,
    allow_vote_changes: poll.allow_vote_changes,
    max_choices: poll.max_choices,
    opens_at: poll.opens_at,
    closes_at: poll.closes_at,
    audiences: poll.audiences,
    options: [...poll.options]
      .sort((a, b) => a.position - b.position)
      .map((option) => option.label),
  };
}
