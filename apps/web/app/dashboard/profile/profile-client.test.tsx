import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { ProfileClient } from "./profile-client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/api", () => ({ api: vi.fn() }));

describe("executive profile authoring", () => {
  it("shows the rich biography editor and searchable organization pickers", async () => {
    vi.mocked(api).mockImplementation(async (path) => {
      if (path === "/api/v1/auth/me") {
        return {
          full_name: "Dr. Ama Owusu",
          email: "ama@example.edu.gh",
          profile_media_id: null,
          staff_id: "UTAG-001",
          title: "Dr.",
          other_name: "Ama",
          surname: "Owusu",
          gender: "Female",
          academic_rank: "Senior Lecturer",
          phone_number: null,
          school_id: null,
          college_id: null,
          department_id: null,
          must_change_password: false,
          must_complete_executive_profile: false,
          roles: ["executive"],
          permissions: ["dashboard.view"],
        };
      }
      if (path === "/api/v1/auth/executive-profile") {
        return {
          id: "appointment-1",
          position: "President",
          portfolio: "Member welfare",
          summary: "Serving members across the University of Ghana.",
          biography_html:
            "<p>Serving members across the University of Ghana.</p>",
          social_links: {},
          term_number: 1,
          is_acting: false,
          is_public: true,
          show_email: false,
          show_phone: false,
          appointed_on: "2024-01-15",
        };
      }
      if (path === "/api/v1/organization/units") {
        return [
          {
            id: "college-1",
            name: "College of Humanities",
            unit_type: "college",
            is_active: true,
          },
          {
            id: "school-1",
            name: "School of Social Sciences",
            unit_type: "school",
            parent_id: "college-1",
            is_active: true,
          },
          {
            id: "department-1",
            name: "Department of Computer Science",
            unit_type: "department",
            parent_id: "school-1",
            is_active: true,
          },
        ];
      }
      throw new Error(`Unhandled test request: ${path}`);
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ProfileClient />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole("tab", { name: "Public leadership" }),
    ).toBeTruthy();
    expect(await screen.findByLabelText("Portfolio")).toBeTruthy();
    expect(await screen.findByLabelText("Public summary")).toBeTruthy();
    expect(await screen.findByLabelText("LinkedIn")).toBeTruthy();
    expect(await screen.findByLabelText("Facebook")).toBeTruthy();
    expect(await screen.findByLabelText("X / Twitter")).toBeTruthy();
    expect(
      await screen.findByLabelText("Personal or office website"),
    ).toBeTruthy();
    const publicEmail = await screen.findByRole("checkbox", {
      name: /Show email publicly/i,
    });
    const publicPhone = await screen.findByRole("checkbox", {
      name: /Show phone publicly/i,
    });
    expect((publicEmail as HTMLInputElement).disabled).toBe(false);
    expect((publicPhone as HTMLInputElement).disabled).toBe(true);
    expect(
      await screen.findByRole("toolbar", { name: "Text formatting" }),
    ).toBeTruthy();
    for (const label of ["School", "College", "Department"]) {
      expect(screen.queryByRole("combobox", { name: label })).toBeNull();
    }
    await screen
      .findByRole("tab", { name: "Account" })
      .then((tab) => tab.click());
    const academicRank = await screen.findByLabelText("Academic rank");
    expect(academicRank.tagName).toBe("SELECT");
    expect((academicRank as HTMLSelectElement).value).toBe("Senior Lecturer");
    for (const label of ["School", "College", "Department"]) {
      expect(
        screen
          .getByRole("combobox", { name: label })
          .getAttribute("aria-expanded"),
      ).toBe("false");
    }
    const college = screen.getByRole("combobox", { name: "College" });
    const school = screen.getByRole("combobox", { name: "School" });
    let department = screen.getByRole("combobox", { name: "Department" });
    await waitFor(() =>
      expect((college as HTMLButtonElement).disabled).toBe(false),
    );
    expect((school as HTMLButtonElement).disabled).toBe(true);
    expect((department as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(college);
    fireEvent.click(
      await screen.findByRole("option", { name: "College of Humanities" }),
    );
    await waitFor(() => expect(document.activeElement).toBe(college));
    expect((school as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(school);
    fireEvent.click(
      await screen.findByRole("option", { name: "School of Social Sciences" }),
    );
    await waitFor(() => expect(document.activeElement).toBe(school));
    await waitFor(() => {
      department = screen.getByRole("combobox", { name: "Department" });
      expect((department as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(department);
    expect(
      await screen.findByRole("option", {
        name: "Department of Computer Science",
      }),
    ).toBeTruthy();
    fireEvent.keyDown(screen.getByPlaceholderText("Search department"), {
      key: "Escape",
    });

    await screen
      .findByRole("tab", { name: "Security" })
      .then((tab) => tab.click());
    expect(
      (await screen.findAllByRole("button", { name: "Show password" })).length,
    ).toBe(3);
  });
});
