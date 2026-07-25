import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceRichTextValue } from "./workspace-rich-text-value";

describe("WorkspaceRichTextValue", () => {
  it("renders stored rich text as formatted content instead of visible markup", () => {
    const { container } = render(
      <WorkspaceRichTextValue html="<p><strong>Executive biography</strong></p>" />,
    );

    expect(container.querySelector("p")?.textContent).toBe(
      "Executive biography",
    );
    expect(container.querySelector("strong")?.textContent).toBe(
      "Executive biography",
    );
    expect(container.textContent).not.toContain("<p>");
  });

  it("shows a human empty state when the stored value is blank", () => {
    const { container } = render(<WorkspaceRichTextValue html="   " />);

    expect(container.textContent).toBe("Not provided");
  });
});
