import { describe, expect, it } from "vitest";

import {
  executiveOfficers,
  isExecutiveOfficerPosition,
  normalizeExecutivePosition,
  sortLeadership,
} from "./leadership";

describe("leadership groups", () => {
  it("recognizes the core executive offices", () => {
    expect(isExecutiveOfficerPosition("President")).toBe(true);
    expect(isExecutiveOfficerPosition("Vice-President")).toBe(true);
    expect(isExecutiveOfficerPosition("Women's Executive Officer")).toBe(true);
  });

  it("normalizes legacy punctuation and spacing", () => {
    expect(isExecutiveOfficerPosition("Women’s Executive\u00a0Officer")).toBe(
      true,
    );
  });

  it("keeps council representatives in the local council group", () => {
    expect(isExecutiveOfficerPosition("CBAS Rep")).toBe(false);
    expect(isExecutiveOfficerPosition("College of Humanities Rep")).toBe(false);
  });

  it("builds the homepage preview from executive officers only", () => {
    const leaders = [
      { position: "Assistant Secretary" },
      { position: "CBAS Rep" },
      { position: "Treasurer" },
      { position: "President" },
      { position: "Vice-President" },
    ];
    expect(executiveOfficers(leaders).map((leader) => leader.position)).toEqual(
      ["President", "Vice-President", "Treasurer"],
    );
  });

  it("follows the established public leadership precedence", () => {
    const leaders = [
      { position: "COH Rep" },
      { position: "Treasurer" },
      { position: "President" },
      { position: "National President" },
      { position: "Vice-President" },
      { position: "Women's Executive Officer" },
      { position: "Secretary" },
      { position: "CBAS Rep" },
      { position: "CHS Rep" },
      { position: "COE Rep" },
    ];
    expect(sortLeadership(leaders).map((leader) => leader.position)).toEqual([
      "President",
      "Vice-President",
      "Secretary",
      "Treasurer",
      "Women's Executive Officer",
      "National President",
      "CBAS Rep",
      "CHS Rep",
      "COE Rep",
      "COH Rep",
    ]);
  });

  it("normalizes aliases before ordering", () => {
    expect(normalizeExecutivePosition("Vice-President")).toBe("vice president");
    expect(normalizeExecutivePosition("Vice President")).toBe("vice president");
    expect(normalizeExecutivePosition("College of Health Rep")).toBe("chs rep");
  });
});
