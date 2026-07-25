import { describe, expect, it } from "vitest";

import { cn, humanize, initials } from "./utils";

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
});
