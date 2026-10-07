import { describe, expect, it } from "vitest";

import { realtimeInvalidationKeys } from "./realtime-provider";

describe("poll realtime query invalidation", () => {
  it("refreshes totals and the member overview on authorized results events", () => {
    expect(
      realtimeInvalidationKeys({ type: "poll.vote.cast", topic: "poll:123:results" }),
    ).toEqual(["polls", "dashboard"]);
  });

  it("refreshes polls, notifications, and the overview for targeted lifecycle events", () => {
    expect(
      realtimeInvalidationKeys({ type: "poll.closed", topic: "user:member-id" }),
    ).toEqual(["notifications", "dashboard", "polls"]);
  });

  it("handles the organizer topic without affecting unrelated caches", () => {
    expect(realtimeInvalidationKeys({ topic: "polls:management" })).toEqual([
      "polls", "dashboard",
    ]);
    expect(realtimeInvalidationKeys({ topic: "conversation:123" })).toEqual(["chat"]);
    expect(realtimeInvalidationKeys({ topic: "members" })).toEqual([
      "members", "dashboard", "analytics",
    ]);
  });

  it("ignores envelopes without a meaningful topic or poll lifecycle", () => {
    expect(realtimeInvalidationKeys({ type: "pong" })).toEqual([]);
  });
});
