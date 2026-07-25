import { describe, expect, it } from "vitest";

import { display, displayChoice } from "../../lib/workspace-display";
import {
  workspaceDetailFields,
  workspaceRowFromMutationResult,
  workspaces,
} from "../../lib/workspaces";

describe("workspace display values", () => {
  it("turns controlled codes into readable labels", () => {
    expect(display("in_review", "status")).toBe("In Review");
    expect(display(["member", "administrator"], "roles")).toBe(
      "Member, Administrator",
    );
  });

  it("never exposes empty structures or UUIDs as raw implementation values", () => {
    expect(display([], "audiences")).toBe("Not provided");
    expect(display({}, "rules")).toBe("Not provided");
    expect(display("[]", "citations")).toBe("Not provided");
    expect(display("f834720e-0df8-4d10-a286-cd082774ced2", "parent_id")).toBe(
      "Internal reference",
    );
  });

  it("formats common file and money values for people", () => {
    expect(display(1_572_864, "byte_size")).toBe("1.5 MB");
    expect(display("application/pdf", "content_type")).toBe("PDF document");
    expect(display(125, "price")).toMatch(/GH₵|GHS/);
  });

  it("turns permission codes into action labels", () => {
    expect(displayChoice("content.publish", "effective_permissions")).toBe(
      "Publish Content",
    );
    expect(displayChoice("members.credentials", "role_permissions")).toBe(
      "Manage member credentials",
    );
  });

  it("uses staff-facing field labels and rich-text metadata in record details", () => {
    const executiveFields = workspaceDetailFields(workspaces.executives);
    const articleFields = workspaceDetailFields(workspaces.news);

    expect(executiveFields.get("biography_html")).toMatchObject({
      label: "Biography",
      type: "richtext",
    });
    expect(articleFields.get("content_html")).toMatchObject({
      label: "Article body",
      type: "richtext",
    });
  });

  it("accepts a saved API record for immediate detail refresh", () => {
    const saved = {
      id: "executive-1",
      full_name: "Dr. Ama Owusu",
      biography_html: "<p>Updated biography</p>",
    };

    expect(workspaceRowFromMutationResult(saved)).toBe(saved);
    expect(workspaceRowFromMutationResult(null)).toBeNull();
    expect(workspaceRowFromMutationResult([])).toBeNull();
  });
});
