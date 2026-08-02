import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { publicApi } from "@/lib/api";

import Home from "./page";

vi.mock("@/lib/api", () => ({ publicApi: vi.fn() }));
vi.mock("@/components/public/home-hero", () => ({
  HomeHero: () => <div>Homepage hero</div>,
}));
vi.mock("@/components/public/public-shell", () => ({
  PublicShell: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("@/components/public/executive-card", () => ({
  ExecutiveCard: ({ profile }: { profile: { full_name: string } }) => (
    <div>{profile.full_name}</div>
  ),
}));

const emptyHome = {
  settings: {},
  featured_articles: [],
  upcoming_events: [],
  leadership: [],
};

const populatedHome = {
  settings: {},
  featured_articles: [
    {
      id: "article-1",
      slug: "association-update",
      title: "Association update",
      excerpt: "An official update for members.",
      tags: ["News"],
      published_at: "2026-08-01T09:00:00Z",
      featured_media_id: null,
    },
  ],
  upcoming_events: [
    {
      id: "event-1",
      slug: "member-forum",
      title: "Member forum",
      short_description: "A forum for members.",
      start_date: "2026-08-12T09:00:00Z",
      event_type: "Meeting",
      venue: "Legon",
      featured_media_id: null,
    },
  ],
  leadership: [
    {
      id: "leader-1",
      full_name: "Professor Ama Mensah",
      title: "Prof.",
      position: "President",
      portfolio: null,
      summary: null,
      biography_html: null,
      social_links: {},
      appointed_on: null,
      ended_on: null,
      term_number: 1,
      is_acting: false,
      is_active: true,
      academic_rank: "Professor",
      profile_media_id: null,
      email: "ama@example.edu.gh",
      phone_number: null,
      school_name: null,
      college_name: null,
      department_name: null,
    },
  ],
};

const populatedGalleries = [
  {
    id: "gallery-1",
    slug: "member-forum",
    title: "Member forum gallery",
    images: [
      {
        id: "image-1",
        url: "/api/v1/public/media/image-1",
        alt_text: "Members at the forum",
        caption: "Forum photographs",
      },
    ],
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("homepage data sections", () => {
  it("omits every data-backed section when it has no items", async () => {
    vi.mocked(publicApi)
      .mockResolvedValueOnce(emptyHome)
      .mockResolvedValueOnce([]);

    render(await Home());

    expect(
      screen.getByRole("heading", {
        name: "A united voice for University of Ghana academics",
      }),
    ).toBeTruthy();
    expect(screen.queryByText("Our events")).toBeNull();
    expect(screen.queryByText("Our gallery")).toBeNull();
    expect(screen.queryByText("Executive officers")).toBeNull();
    expect(screen.queryByText("Our news")).toBeNull();
    expect(screen.queryByRole("link", { name: /view all events/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /view all news/i })).toBeNull();
    expect(
      screen.queryByRole("link", { name: /open member portal/i }),
    ).toBeNull();
  });

  it("renders each data-backed section when it has usable content", async () => {
    vi.mocked(publicApi)
      .mockResolvedValueOnce(populatedHome)
      .mockResolvedValueOnce(populatedGalleries);

    render(await Home());

    expect(screen.getByText("Our events")).toBeTruthy();
    expect(screen.getByText("Our gallery")).toBeTruthy();
    expect(screen.getByText("Executive officers")).toBeTruthy();
    expect(screen.getByText("Our news")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Member forum" })).toBeTruthy();
    expect(screen.getByText("Professor Ama Mensah")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Association update" }),
    ).toBeTruthy();
  });
});
