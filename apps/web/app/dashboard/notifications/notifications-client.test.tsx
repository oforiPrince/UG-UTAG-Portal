import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { NotificationsClient } from "./notifications-client";

vi.mock("@/lib/api", () => ({ api: vi.fn() }));

const mockedApi = vi.mocked(api);

describe("notification authoring", () => {
  beforeEach(() => {
    mockedApi.mockImplementation(async (path) => {
      if (path === "/api/v1/auth/me") {
        return { permissions: ["notifications.manage"] };
      }
      if (path.startsWith("/api/v1/notifications")) {
        return { items: [] };
      }
      if (path.startsWith("/api/v1/members")) {
        return { items: [] };
      }
      throw new Error(`Unhandled test request: ${path}`);
    });
  });

  it("uses a prominent title and the shared rich-text editor", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <NotificationsClient />
      </QueryClientProvider>,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Send direct alert" }),
    );

    expect(
      screen.getByText(/Use this for a one-off alert to selected members/i),
    ).toBeTruthy();
    const title = screen.getByPlaceholderText("Enter the alert title");
    expect(title.className).toContain("min-h-15");
    expect(
      await screen.findByRole("toolbar", { name: "Text formatting" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("textbox", { name: /message/i })
        .getAttribute("aria-multiline"),
    ).toBe("true");
  });

  it("renders formatted notification messages instead of raw HTML", async () => {
    mockedApi.mockImplementation(async (path) => {
      if (path === "/api/v1/auth/me") {
        return { permissions: [] };
      }
      if (path.startsWith("/api/v1/notifications")) {
        return {
          items: [
            {
              id: "notification-1",
              category: "announcement",
              priority: "normal",
              title: "Member update",
              body: "<p>Please read the <strong>association update</strong>.</p>",
              deep_link: null,
              read_at: null,
              created_at: new Date().toISOString(),
            },
          ],
        };
      }
      throw new Error(`Unhandled test request: ${path}`);
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <NotificationsClient />
      </QueryClientProvider>,
    );

    expect((await screen.findByText("association update")).tagName).toBe(
      "STRONG",
    );
    expect(container.textContent).not.toContain("<strong>");
    expect(screen.getByText(/Official announcement/)).toBeTruthy();
  });
});
