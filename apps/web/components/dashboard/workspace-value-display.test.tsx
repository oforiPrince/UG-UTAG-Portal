import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ValueDisplay } from "@/components/dashboard/workspace-client";

afterEach(cleanup);

describe("workspace value display", () => {
  it("presents audience rules as human labels", () => {
    render(
      <ValueDisplay
        fieldKey="audiences"
        value={[{ type: "role", value: "member" }, { type: "general_public" }]}
      />,
    );

    expect(screen.getByText("Members")).toBeTruthy();
    expect(screen.getByText("General public")).toBeTruthy();
    expect(screen.queryByText(/Item 1/)).toBeNull();
  });

  it("keeps compact datetimes on one line", () => {
    render(
      <ValueDisplay
        compact
        fieldKey="starts_at"
        value="2026-09-03T00:00:00Z"
      />,
    );

    const value = screen.getByText(/2026/);
    expect(value.className).toContain("whitespace-nowrap");
    expect(value.textContent).toMatch(/2026/);
    expect(value.textContent).toMatch(/\d{1,2}:\d{2}/);
    expect(value.textContent).not.toMatch(/\n/);
  });

  it("can hide time from compact schedule dates", () => {
    render(
      <ValueDisplay
        compact
        dateStyle="date"
        fieldKey="starts_at"
        value="2026-08-02T00:00:00Z"
      />,
    );

    const value = screen.getByText(/Aug 2026/);
    expect(value.className).toContain("whitespace-nowrap");
    expect(value.textContent).not.toMatch(/\d{1,2}:\d{2}/);
  });
});
