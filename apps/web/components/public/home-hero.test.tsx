import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HomeHero, type HomeCarouselSlide } from "./home-hero";

const slide: HomeCarouselSlide = {
  id: "slide-1",
  title: "Member solidarity",
  description:
    "<p>Working with <strong>members</strong> across the University.</p>",
  media_asset_id: "media-1",
  link_url: null,
  order: 1,
  is_published: true,
};

describe("HomeHero", () => {
  it("renders the sanitized carousel description as formatted content", () => {
    const { container } = render(<HomeHero slides={[slide]} />);

    expect(container.querySelector("strong")?.textContent).toBe("members");
    expect(container.textContent).not.toContain("<strong>");
  });
});
