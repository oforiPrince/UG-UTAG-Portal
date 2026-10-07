import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MutationForm } from "@/components/dashboard/workspace-client";
import { api } from "@/lib/api";
import type { WorkspaceWizardStep } from "@/lib/workspace-presentation";
import type { WorkspaceConfig, WorkspaceMutation } from "@/lib/workspaces";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: vi.fn() };
});

afterEach(cleanup);

const config: WorkspaceConfig = {
  key: "test",
  title: "Test records",
  description: "Test records",
  endpoint: "/api/v1/test",
  queryKey: "test",
  columns: [{ key: "title", label: "Title" }],
};

const mutation: WorkspaceMutation = {
  label: "Create record",
  permission: "test.manage",
  endpoint: "/api/v1/test",
  fields: [
    { key: "title", label: "Title", required: true },
    { key: "summary", label: "Summary", type: "textarea" },
  ],
  successMessage: "Record created",
};

const steps: WorkspaceWizardStep[] = [
  {
    id: "details",
    title: "Details",
    description: "Add the essential information.",
    fieldKeys: ["title", "summary"],
  },
  {
    id: "review",
    title: "Review and save",
    description: "Check the information before saving.",
    fieldKeys: [],
  },
];

describe("workspace guided form", () => {
  it("keeps full-page forms anchored at the page heading", () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MutationForm
          config={config}
          mutation={mutation}
          mode="create"
          permissions={["test.manage"]}
          steps={steps}
          variant="page"
          close={vi.fn()}
        />
      </QueryClientProvider>,
    );

    expect(document.activeElement).not.toBe(screen.getByLabelText(/Title/));
    const heading = screen.getByRole("heading", { name: "Create record" });
    expect(heading.className).not.toMatch(/text-(4|5|6)xl/);
    expect(heading.className).toMatch(/text-xl/);
  });

  it("submits only after the final review step", async () => {
    vi.mocked(api).mockResolvedValue({
      id: "record-1",
      title: "Annual report",
    });
    const onSaved = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MutationForm
          config={config}
          mutation={mutation}
          mode="create"
          permissions={["test.manage"]}
          steps={steps}
          close={vi.fn()}
          onSaved={onSaved}
        />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText(/Title/), {
      target: { value: "Annual report" },
    });
    fireEvent.change(screen.getByLabelText("Summary"), {
      target: { value: "Association activity for the year." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(api).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Review and save" }),
    ).toBeTruthy();
    expect(screen.getByText("Annual report")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Edit Title" }));
    expect(screen.getByLabelText(/Title/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Review and save" }));
    expect(
      screen.getByRole("heading", { name: "Review and save" }),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Create record/ }));

    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/api/v1/test", {
        method: "POST",
        headers: undefined,
        body: {
          title: "Annual report",
          summary: "Association activity for the year.",
        },
      }),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
  });
});
