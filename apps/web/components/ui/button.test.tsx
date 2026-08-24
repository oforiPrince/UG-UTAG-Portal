import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("keeps the primary hover surface tied to the active theme", () => {
    render(<Button>Save changes</Button>);

    const button = screen.getByRole("button", { name: "Save changes" });
    expect(button.className).toContain("hover:bg-ink/85");
    expect(button.className).not.toContain("hover:bg-[#183052]");
  });
});
