import { describe, expect, it } from "vitest";

import {
  detailFieldValue,
  visibleDetailEntries,
  workspaceDetails,
} from "./workspace-detail";

describe("workspace detail field sets", () => {
  const eventRow = {
    title: "2026 UTAG FAMILY GET-TOGETHER",
    slug: "2026-utag-family-get-together",
    short_description: "",
    description_html: "",
    start_date: "2026-01-10",
    end_date: "2026-01-10",
    start_time: "10:30:00",
    end_time: "17:00:00",
    timezone: "Africa/Accra",
    event_type: "meeting",
    status: "completed",
    publication_status: "published",
    registered: false,
  };

  it("hides empty and staff fields from member event details", () => {
    const entries = visibleDetailEntries(eventRow, workspaceDetails.events, [
      "dashboard.view",
    ]);
    const labels = entries.map((entry) => entry.field.label);
    expect(labels).toContain("When");
    expect(labels).not.toContain("Slug");
    expect(labels).not.toContain("Summary");
    expect(labels).not.toContain("Description");
    expect(
      detailFieldValue(eventRow, workspaceDetails.events.fields[0]!),
    ).toContain("10:30 AM");
  });

  it("includes manage fields when the user can manage events", () => {
    const entries = visibleDetailEntries(eventRow, workspaceDetails.events, [
      "dashboard.view",
      "events.manage",
    ]);
    expect(entries.some((entry) => entry.field.key === "slug")).toBe(true);
    expect(
      entries.some((entry) => entry.field.key === "publication_status"),
    ).toBe(true);
  });
});
