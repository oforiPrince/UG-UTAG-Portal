import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceClient } from "@/components/dashboard/workspace-client";
import { api } from "@/lib/api";
import { workspaces } from "@/lib/workspaces";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/dashboard/members",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: vi.fn() };
});

afterEach(cleanup);

function renderWorkspace(config = workspaces.members) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkspaceClient config={config} />
    </QueryClientProvider>,
  );
}

describe("workspace list chrome", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders members as a dense table without a duplicate page intro", async () => {
    vi.mocked(api).mockImplementation((async (path: string) => {
      if (path === "/api/v1/auth/me") {
        return {
          id: "admin-1",
          permissions: ["members.view", "members.create", "members.export"],
        };
      }
      if (path === "/api/v1/public/capabilities") {
        return { email_delivery: false, sms_delivery: false };
      }
      return {
        items: [
          {
            id: "member-1",
            full_name: "Ama Owusu",
            email: "ama@example.com",
            academic_rank: "senior_lecturer",
            status: "active",
            roles: ["member"],
            school_name: "School of Engineering",
          },
        ],
        page: 1,
        total: 21,
        pages: 2,
      };
    }) as typeof api);

    renderWorkspace(workspaces.members);

    expect(
      await screen.findByRole("button", { name: "Create member" }),
    ).toBeTruthy();
    expect(screen.getByPlaceholderText("Search members")).toBeTruthy();
    expect(screen.getByText("21 members on file")).toBeTruthy();
    expect(screen.getByRole("table", { name: "All members" })).toBeTruthy();
    expect(screen.getByText("ama@example.com")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Member" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Email" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Rank" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Status" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "School" })).toBeNull();
    expect(screen.getByRole("button", { name: "View" }).className).toContain(
      "h-7",
    );
    expect(screen.getByRole("button", { name: "View" }).textContent).toBe("");
    expect(
      screen.queryByRole("heading", { name: "All members" }),
    ).toBeNull();
    expect(
      screen.queryByRole("heading", { name: "Ama Owusu" }),
    ).toBeNull();
    expect(
      screen.queryByText(/One account directory for members and administrators/),
    ).toBeNull();
  });

  it("renders executive appointments as a dense table without a duplicate page intro", async () => {
    vi.mocked(api).mockImplementation((async (path: string) => {
      if (path === "/api/v1/auth/me") {
        return {
          id: "admin-1",
          permissions: ["executives.manage", "members.export"],
        };
      }
      if (path === "/api/v1/public/capabilities") {
        return { email_delivery: false, sms_delivery: false };
      }
      return {
        items: [
          {
            id: "exec-1",
            full_name: "Kwame Mensah",
            position: "Chairperson",
            portfolio: "Leadership",
            term_number: 1,
            is_active: true,
          },
        ],
        page: 1,
        page_size: 15,
        total: 16,
        pages: 2,
      };
    }) as typeof api);

    renderWorkspace(workspaces.executives);

    expect(
      await screen.findByRole("button", { name: "Add appointment" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("table", { name: "Executive appointments" }),
    ).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Position" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Current" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "Portfolio" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Term" })).toBeNull();
    expect(screen.getByText("Chairperson")).toBeTruthy();
    expect(screen.getByText("Yes").className).toContain("workspace-table-chip");
    expect(screen.getByText("Yes").className).toContain("w-fit");
    expect(screen.getByRole("button", { name: "View" }).className).toContain(
      "h-7",
    );
    expect(screen.getByRole("button", { name: "View" }).textContent).toBe("");
    expect(screen.queryByRole("button", { name: "End appointment" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    expect(screen.getByRole("menuitem", { name: "End appointment" })).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: "Executive appointments" }),
    ).toBeNull();
    expect(
      screen.queryByRole("heading", { name: "Kwame Mensah" }),
    ).toBeNull();
    expect(
      screen.queryByText(/Current and past leadership terms/),
    ).toBeNull();
    expect(screen.getByText("16 executives on file")).toBeTruthy();
    expect(screen.getByText("Page 1 of 2")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Previous page" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.getByRole("button", { name: "Next page" }).hasAttribute("disabled")).toBe(
      false,
    );
  });

  it("renders advert campaigns as a dense data table", async () => {
    vi.mocked(api).mockImplementation((async (path: string) => {
      if (path === "/api/v1/auth/me") {
        return {
          id: "admin-1",
          permissions: ["adverts.manage", "adverts.view"],
        };
      }
      if (path === "/api/v1/public/capabilities") {
        return { email_delivery: false, sms_delivery: false };
      }
      return {
        items: [
          {
            id: "campaign-1",
            title: "Site footer · 30 days · Campus Bank Ghana",
            placement_name: "Site footer strip",
            fulfilment: "Paid · ready",
            advertiser_name: "Campus Bank Ghana",
            status: "active",
            starts_at: "2026-08-02T00:00:00Z",
            impressions: 101,
            clicks: 0,
          },
        ],
      };
    }) as typeof api);

    renderWorkspace(workspaces.adverts);

    expect(
      await screen.findByRole("button", { name: "New campaign" }),
    ).toBeTruthy();
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Campaign" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Status" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Schedule" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Delivery" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "Advertiser" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Placement" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Fulfilment" })).toBeNull();
    expect(
      screen.queryByRole("columnheader", { name: "Impressions" }),
    ).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Clicks" })).toBeNull();
    expect(screen.getByText("Site footer · 30 days")).toBeTruthy();
    expect(
      screen.queryByText("Site footer · 30 days · Campus Bank Ghana"),
    ).toBeNull();
    expect(screen.getByText("Campus Bank Ghana")).toBeTruthy();
    expect(screen.getByText("Paid · ready")).toBeTruthy();
    expect(screen.getByLabelText("101 impressions, 0 clicks")).toBeTruthy();
    expect(
      screen.queryByRole("heading", {
        name: "Site footer · 30 days",
      }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: "View" }).className).toContain(
      "h-7",
    );
    expect(screen.queryByRole("button", { name: "Complete campaign" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    expect(
      screen.getByRole("menuitem", { name: "Complete campaign" }),
    ).toBeTruthy();
  });

  it("presents analytics as grouped snapshot KPIs instead of catalog cards", async () => {
    vi.mocked(api).mockImplementation((async (path: string) => {
      if (path === "/api/v1/auth/me") {
        return { id: "admin-1", permissions: ["analytics.view"] };
      }
      if (path === "/api/v1/public/capabilities") {
        return { email_delivery: false, sms_delivery: false };
      }
      return {
        generated_at: "2026-09-03T20:02:00Z",
        members: { total: 21, active: 21, new_30_days: 1 },
        content: { published_articles: 1, documents: 2 },
        events: { total: 1, registrations: 2 },
      };
    }) as typeof api);

    renderWorkspace(workspaces.analytics);

    expect(await screen.findByText(/Snapshot as of/)).toBeTruthy();
    expect(screen.getAllByRole("heading", { name: "Members" }).length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByRole("heading", { name: "Content" }).length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByRole("heading", { name: "Events" }).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText("New in 30 days")).toBeTruthy();
    expect(screen.getByText("Published articles")).toBeTruthy();
    expect(screen.queryByPlaceholderText("Search metrics")).toBeNull();
    expect(screen.queryByText("Generated At")).toBeNull();
    expect(screen.queryByRole("button", { name: "View" })).toBeNull();
    expect(screen.queryByText("metrics on file")).toBeNull();
  });

  it("presents audit entries as a dense log table", async () => {
    vi.mocked(api).mockImplementation((async (path: string) => {
      if (path === "/api/v1/auth/me") {
        return { id: "admin-1", permissions: ["audit.view"] };
      }
      if (path === "/api/v1/public/capabilities") {
        return { email_delivery: false, sms_delivery: false };
      }
      return {
        items: [
          {
            id: "audit-1",
            actor_name: "Dr. Kwame Ofori",
            action: "chat.conversation.read",
            resource_type: "conversation",
            outcome: "success",
            created_at: "2026-09-03T20:00:00Z",
          },
          {
            id: "audit-2",
            actor_name: "Dr. Kwame Ofori",
            action: "notification.deleted",
            resource_type: "notification",
            outcome: "success",
            created_at: "2026-09-03T19:58:00Z",
          },
        ],
        page: 1,
        total: 2,
        pages: 1,
      };
    }) as typeof api);

    renderWorkspace(workspaces.audit);

    expect(await screen.findByRole("table")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Actor" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Action" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Time" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Outcome" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "Subject" })).toBeNull();
    expect(screen.getByText("Chat Conversation Read")).toBeTruthy();
    expect(screen.getByText("Conversation")).toBeTruthy();
    expect(screen.getAllByText("Success")[0]?.className).toContain("w-fit");
    expect(screen.getByPlaceholderText("Search audit entries")).toBeTruthy();
    expect(
      screen.getAllByRole("button", { name: "View" })[0]?.className,
    ).toContain("h-7");
    expect(
      screen.queryByRole("heading", { name: "Chat Conversation Read" }),
    ).toBeNull();
  });
});
