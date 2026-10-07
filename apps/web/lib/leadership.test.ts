import { describe, expect, it } from "vitest";

import {
  executiveOfficers,
  formatExecutivePosition,
  isExecutiveOfficerPosition,
  normalizeExecutivePosition,
  publishedExecutiveEmail,
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

  it("shows abbreviated college rep labels on the public site", () => {
    expect(formatExecutivePosition("College of Health Rep")).toBe("CHS Rep");
    expect(formatExecutivePosition("College of Humanities Rep")).toBe("COH Rep");
    expect(formatExecutivePosition("College of Education Rep")).toBe("COE Rep");
    expect(formatExecutivePosition("CHS Rep")).toBe("CHS Rep");
    expect(formatExecutivePosition("CBAS Rep")).toBe("CBAS Rep");
    expect(formatExecutivePosition("Vice-President")).toBe("Vice-President");
  });
});

describe("published executive contact", () => {
  it("withholds email when the office-holder has opted out", () => {
    expect(
      publishedExecutiveEmail({
        email: "ksadu-manu@ug.edu.gh",
        show_email: false,
      }),
    ).toBeNull();
  });

  it("returns a consented email", () => {
    expect(
      publishedExecutiveEmail({
        email: " ksadu-manu@ug.edu.gh ",
        show_email: true,
      }),
    ).toBe("ksadu-manu@ug.edu.gh");
  });
});
