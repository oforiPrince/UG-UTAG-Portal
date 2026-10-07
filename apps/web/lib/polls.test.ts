import { describe, expect, it } from "vitest";

import {
  accraInputToUtc,
  audienceKey,
  INDUSTRIAL_ACTION_TEMPLATE,
  pollCountdown,
  pollRules,
  togglePollChoice,
  utcToAccraInput,
} from "./polls";

describe("poll schedules and ballot rules", () => {
  it("interprets explicitly labelled Accra times as UTC without device timezone shifts", () => {
    expect(accraInputToUtc("2026-10-07T17:30")).toBe(
      "2026-10-07T17:30:00.000Z",
    );
    expect(utcToAccraInput("2026-10-07T19:30:00+02:00")).toBe(
      "2026-10-07T17:30",
    );
    expect(accraInputToUtc("")).toBeNull();
    expect(accraInputToUtc("2026-02-31T12:00")).toBeNull();
  });

  it("replaces single answers and bounds multiple selections without losing an existing vote", () => {
    expect(togglePollChoice(["yes"], "no", "single", 1)).toEqual(["no"]);
    expect(togglePollChoice(["a", "b"], "c", "multiple", 2)).toEqual([
      "a",
      "b",
    ]);
    expect(togglePollChoice(["a", "b"], "a", "multiple", 2)).toEqual(["b"]);
  });

  it("makes privacy, result visibility, and finality explicit", () => {
    const confidential = pollRules({
      privacy: "confidential",
      results_visibility: "after_close",
      allow_vote_changes: false,
    });
    expect(confidential.privacy).toContain("aggregate");
    expect(confidential.results).toContain("when the poll closes");
    expect(confidential.changes).toContain("final");
    expect(
      pollRules({
        privacy: "named",
        results_visibility: "after_vote",
        allow_vote_changes: true,
      }).privacy,
    ).toContain("name and choices");
  });

  it("uses the corrected time to explain the deadline and never displays negative time", () => {
    const now = Date.parse("2026-10-07T12:00:00Z");
    expect(pollCountdown("2026-10-07T13:15:00Z", now)).toBe("1h 15m remaining");
    expect(pollCountdown("2026-10-07T11:59:00Z", now)).toBe(
      "Time window ended",
    );
  });

  it("keeps the requested industrial action question and exact answer choices", () => {
    expect(INDUSTRIAL_ACTION_TEMPLATE.question).toContain(
      "full payment of both Promotion Arrears and BRA?",
    );
    expect(INDUSTRIAL_ACTION_TEMPLATE.options).toEqual([
      "YES, I support the industrial action",
      "NO, I do not support the industrial action",
    ]);
    expect(audienceKey({ type: "school", value: "1" })).not.toBe(
      audienceKey({ type: "department", value: "1" }),
    );
  });
});
