const EXECUTIVE_POSITION_ORDER = [
  "president",
  "vice president",
  "secretary",
  "treasurer",
  "women's executive officer",
] as const;

const POSITION_ALIASES: Record<string, string> = {
  "college of humanities rep": "coh rep",
  "college of health rep": "chs rep",
  "college of education rep": "coe rep",
};

/** Canonical public labels for college reps (legacy full names still exist in data). */
const POSITION_DISPLAY_LABELS: Record<string, string> = {
  "coh rep": "COH Rep",
  "chs rep": "CHS Rep",
  "coe rep": "COE Rep",
  "cbas rep": "CBAS Rep",
};

const PUBLIC_POSITION_ORDER = [
  ...EXECUTIVE_POSITION_ORDER,
  "national president",
  "cbas rep",
  "chs rep",
  "coe rep",
  "coh rep",
] as const;

const POSITION_ORDER_INDEX = new Map<string, number>(
  PUBLIC_POSITION_ORDER.map((position, index) => [position, index]),
);

export type PublicExecutiveProfile = {
  id: string;
  full_name: string;
  title: string;
  position: string;
  portfolio: string | null;
  summary: string | null;
  biography_html: string | null;
  social_links: Record<string, string>;
  appointed_on: string | null;
  ended_on: string | null;
  term_number: number;
  is_acting: boolean;
  is_active: boolean;
  academic_rank: string | null;
  profile_media_id: string | null;
  email: string;
  phone_number: string | null;
  school_name: string | null;
  college_name: string | null;
  department_name: string | null;
};

export function normalizeExecutivePosition(position: string) {
  const normalized = position
    .replace(/[’‘]/g, "'")
    .replace(/\u00a0/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
  return POSITION_ALIASES[normalized] ?? normalized;
}

/** Short public label for leadership cards (e.g. College of Health Rep → CHS Rep). */
export function formatExecutivePosition(position: string) {
  const normalized = normalizeExecutivePosition(position);
  if (POSITION_DISPLAY_LABELS[normalized]) {
    return POSITION_DISPLAY_LABELS[normalized];
  }
  return position.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

export function isExecutiveOfficerPosition(position: string) {
  return EXECUTIVE_POSITION_ORDER.includes(
    normalizeExecutivePosition(
      position,
    ) as (typeof EXECUTIVE_POSITION_ORDER)[number],
  );
}

export function executivePositionOrder(position: string) {
  const normalized = normalizeExecutivePosition(position);
  return {
    index: POSITION_ORDER_INDEX.get(normalized) ?? POSITION_ORDER_INDEX.size,
    normalized,
  };
}

export function sortLeadership<
  T extends { position: string; full_name?: string },
>(leaders: T[]) {
  return [...leaders].sort((left, right) => {
    const leftOrder = executivePositionOrder(left.position);
    const rightOrder = executivePositionOrder(right.position);
    return (
      leftOrder.index - rightOrder.index ||
      leftOrder.normalized.localeCompare(rightOrder.normalized) ||
      (left.full_name ?? "").localeCompare(right.full_name ?? "")
    );
  });
}

export function executiveOfficers<
  T extends { position: string; full_name?: string },
>(leaders: T[]) {
  return sortLeadership(leaders).filter((leader) =>
    isExecutiveOfficerPosition(leader.position),
  );
}
