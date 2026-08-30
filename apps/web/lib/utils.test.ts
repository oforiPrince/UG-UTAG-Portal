import { describe, expect, it } from "vitest";

import {
  cn,
  formatPersonName,
  formatRankForName,
  humanize,
  initials,
  matchCaseStyle,
} from "./utils";

describe("display utilities", () => {
  it("builds readable initials", () => {
    expect(initials("Dr. Ama Mensah")).toBe("DA");
  });

  it("humanizes event keys", () => {
    expect(humanize("document.version_created")).toBe("Document Version Created");
  });

  it("merges conflicting Tailwind classes", () => {
    expect(cn("px-2", "px-4")).toContain("px-4");
  });

  it("uppercases ranks when the name is uppercase", () => {
    expect(
      formatRankForName(
        "Prof. EMMANUEL OFOSU-MENSAH ABABIO",
        "Senior Lecturer",
      ),
    ).toBe("SENIOR LECTURER");
    expect(
      matchCaseStyle("DANLADI ABAH", "lecturer"),
    ).toBe("LECTURER");
  });

  it("title-cases ranks when the name is title case", () => {
    expect(formatRankForName("Dr. Ama Mensah", "SENIOR LECTURER")).toBe(
      "Senior Lecturer",
    );
  });

  it("aligns honorific casing with the name body", () => {
    expect(formatPersonName("Prof. EMMANUEL OFOSU-MENSAH ABABIO")).toBe(
      "PROF. EMMANUEL OFOSU-MENSAH ABABIO",
    );
    expect(formatPersonName("dr. Ama Mensah")).toBe("Dr. Ama Mensah");
  });
});
