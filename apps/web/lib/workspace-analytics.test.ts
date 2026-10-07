import { describe, expect, it } from "vitest";

import {
  analyticsSnapshotFrom,
  formatAnalyticsValue,
} from "./workspace-analytics";

const payload = {
  generated_at: "2026-09-03T20:02:00Z",
  members: { total: 21, active: 21, new_30_days: 1 },
  content: { published_articles: 1, documents: 2 },
  events: { total: 1, registrations: 2 },
};

describe("analytics snapshot", () => {
  it("groups the association snapshot and keeps generated_at as metadata", () => {
    const snapshot = analyticsSnapshotFrom(payload);

    expect(snapshot.generatedAt).toBe("2026-09-03T20:02:00Z");
    expect(snapshot.groups.map((group) => group.id)).toEqual([
      "members",
      "content",
      "events",
    ]);
    expect(snapshot.groups[0]?.metrics).toEqual([
      { key: "total", label: "Total", value: 21 },
      { key: "active", label: "Active", value: 21 },
      { key: "new_30_days", label: "New in 30 days", value: 1 },
    ]);
    expect(
      snapshot.groups.some((group) => group.id === "generated_at"),
    ).toBe(false);
  });

  it("formats counts with ordinary numerals", () => {
    expect(formatAnalyticsValue(21)).toBe("21");
    expect(formatAnalyticsValue(1240)).toBe("1,240");
  });

  it("returns an empty snapshot for unexpected payloads", () => {
    expect(analyticsSnapshotFrom(null)).toEqual({
      generatedAt: null,
      groups: [],
    });
    expect(analyticsSnapshotFrom([])).toEqual({
      generatedAt: null,
      groups: [],
    });
  });
});
