import { humanize } from "./utils";

export type AnalyticsMetric = {
  key: string;
  label: string;
  value: number | string;
};

export type AnalyticsGroup = {
  id: string;
  label: string;
  metrics: AnalyticsMetric[];
};

export type AnalyticsSnapshot = {
  generatedAt: string | null;
  groups: AnalyticsGroup[];
};

const GROUP_ORDER = ["members", "content", "events"] as const;

const GROUP_LABELS: Record<string, string> = {
  members: "Members",
  content: "Content",
  events: "Events",
};

const METRIC_LABELS: Record<string, string> = {
  total: "Total",
  active: "Active",
  new_30_days: "New in 30 days",
  published_articles: "Published articles",
  documents: "Documents",
  registrations: "Registrations",
};

function metricLabel(key: string) {
  return METRIC_LABELS[key] ?? humanize(key);
}

function metricValue(value: unknown): number | string | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : value;
  }
  return null;
}

export function formatAnalyticsValue(value: number | string) {
  if (typeof value === "number") {
    return new Intl.NumberFormat("en-GH").format(value);
  }
  return value;
}

export function analyticsSnapshotFrom(data: unknown): AnalyticsSnapshot {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { generatedAt: null, groups: [] };
  }

  const record = data as Record<string, unknown>;
  const generatedAt =
    typeof record.generated_at === "string" && record.generated_at
      ? record.generated_at
      : null;

  const known = new Set<string>(GROUP_ORDER);
  const orderedIds = [
    ...GROUP_ORDER.filter((id) => record[id] && typeof record[id] === "object"),
    ...Object.keys(record).filter(
      (id) =>
        !known.has(id) &&
        id !== "generated_at" &&
        record[id] &&
        typeof record[id] === "object" &&
        !Array.isArray(record[id]),
    ),
  ];

  const groups = orderedIds.flatMap((id) => {
    const raw = record[id];
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
    const metrics = Object.entries(raw as Record<string, unknown>).flatMap(
      ([key, item]) => {
        const value = metricValue(item);
        if (value == null) return [];
        return [{ key, label: metricLabel(key), value }];
      },
    );
    if (!metrics.length) return [];
    return [
      {
        id,
        label: GROUP_LABELS[id] ?? humanize(id),
        metrics,
      },
    ];
  });

  return { generatedAt, groups };
}
