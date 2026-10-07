import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorkspaceField } from "@/lib/workspaces";

import { WorkspaceSelect } from "./workspace-client";

const originalInnerHeight = window.innerHeight;
const originalInnerWidth = window.innerWidth;

afterEach(() => {
  cleanup();
  document.querySelector("[data-dashboard-bottom-nav]")?.remove();
  Object.defineProperty(window, "innerHeight", {
    configurable: true,
    value: originalInnerHeight,
  });
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: originalInnerWidth,
  });
});

function renderSelect(field: WorkspaceField, onChange = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <span id="department-label">Department</span>
      <WorkspaceSelect
        id="department"
        labelledBy="department-label"
        field={field}
        value=""
        autoFocus={false}
        onChange={onChange}
      />
    </QueryClientProvider>,
  );
  return { ...result, onChange };
}

describe("WorkspaceSelect", () => {
  it("portals a bounded menu above a trigger near the viewport bottom", async () => {
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 600,
    });
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 900,
    });
    const field: WorkspaceField = {
      key: "department_id",
      label: "Department",
      type: "select",
      options: Array.from(
        { length: 18 },
        (_, index) => `Department ${index + 1}`,
      ),
    };
    const { container } = renderSelect(field);
    const trigger = screen.getByRole("combobox", { name: "Department" });
    vi.spyOn(trigger, "getBoundingClientRect").mockReturnValue({
      x: 420,
      y: 520,
      top: 520,
      right: 720,
      bottom: 568,
      left: 420,
      width: 300,
      height: 48,
      toJSON: () => ({}),
    });

    fireEvent.click(trigger);

    const listbox = await screen.findByRole("listbox", { name: "Department" });
    const menu = listbox.parentElement;
    expect(menu?.dataset.placement).toBe("top");
    expect(Number.parseFloat(menu?.style.top ?? "600")).toBeLessThan(520);
    expect(Number.parseFloat(menu?.style.maxHeight ?? "0")).toBeLessThanOrEqual(
      320,
    );
    expect(listbox.className).toContain("overflow-y-auto");
    expect(listbox.className).toContain("overscroll-contain");
    expect(container.contains(menu)).toBe(false);
  });

  it("keeps the menu above the fixed mobile navigation", async () => {
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 800,
    });
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 390,
    });
    const navigation = document.createElement("nav");
    navigation.dataset.dashboardBottomNav = "";
    document.body.append(navigation);
    vi.spyOn(navigation, "getBoundingClientRect").mockReturnValue({
      x: 12,
      y: 600,
      top: 600,
      right: 378,
      bottom: 680,
      left: 12,
      width: 366,
      height: 80,
      toJSON: () => ({}),
    });
    const field: WorkspaceField = {
      key: "department_id",
      label: "Department",
      type: "select",
      options: Array.from(
        { length: 18 },
        (_, index) => `Department ${index + 1}`,
      ),
    };
    renderSelect(field);
    const trigger = screen.getByRole("combobox", { name: "Department" });
    vi.spyOn(trigger, "getBoundingClientRect").mockReturnValue({
      x: 22,
      y: 440,
      top: 440,
      right: 368,
      bottom: 488,
      left: 22,
      width: 346,
      height: 48,
      toJSON: () => ({}),
    });

    fireEvent.click(trigger);

    const listbox = await screen.findByRole("listbox", { name: "Department" });
    const menu = listbox.parentElement;
    const menuTop = Number.parseFloat(menu?.style.top ?? "0");
    const menuMaxHeight = Number.parseFloat(menu?.style.maxHeight ?? "0");
    expect(menu?.dataset.placement).toBe("top");
    expect(menuTop + menuMaxHeight).toBeLessThanOrEqual(588);
  });

  it("supports searching and keyboard selection without moving focus into the list", async () => {
    const field: WorkspaceField = {
      key: "department_id",
      label: "Department",
      type: "select",
      options: [
        "Department of Computer Engineering",
        "Department of Computer Science",
        ...Array.from({ length: 10 }, (_, index) => `Department ${index + 1}`),
      ],
    };
    const { onChange } = renderSelect(field);
    const trigger = screen.getByRole("combobox", { name: "Department" });
    fireEvent.click(trigger);
    const search = await screen.findByPlaceholderText("Search department");
    fireEvent.change(search, { target: { value: "computer" } });
    fireEvent.keyDown(search, { key: "ArrowDown" });
    fireEvent.keyDown(search, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith("Department of Computer Science");
    await waitFor(() => {
      expect(trigger.getAttribute("aria-expanded")).toBe("false");
      expect(document.activeElement).toBe(trigger);
    });
  });
});
