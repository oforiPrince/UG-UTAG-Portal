import { describe, expect, it } from "vitest";

import { normalizeEditorHtml, normalizeLinkHref } from "../../lib/rich-text";

describe("rich text editor values", () => {
  it("stores a truly empty editor as an empty value", () => {
    expect(normalizeEditorHtml("")).toBe("");
    expect(normalizeEditorHtml("<p></p>")).toBe("");
    expect(normalizeEditorHtml("<p>Association update</p>")).toBe(
      "<p>Association update</p>",
    );
  });

  it("normalizes safe links and rejects active protocols", () => {
    expect(normalizeLinkHref("utag.ug.edu.gh")).toBe("https://utag.ug.edu.gh");
    expect(normalizeLinkHref("office@utag.ug.edu.gh")).toBe(
      "mailto:office@utag.ug.edu.gh",
    );
    expect(normalizeLinkHref("https://ug.edu.gh/news")).toBe(
      "https://ug.edu.gh/news",
    );
    expect(normalizeLinkHref("javascript:alert(1)")).toBeNull();
    expect(normalizeLinkHref("not a website")).toBeNull();
  });
});
