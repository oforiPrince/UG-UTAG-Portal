import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { NotificationBell } from "./notification-bell";

vi.mock("@/lib/api", () => ({ api: vi.fn() }));
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const mockedApi = vi.mocked(api);

describe("NotificationBell", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    mockedApi.mockReset();
    mockedApi.mockImplementation(async (path) => {
      if (path === "/api/v1/notifications/unread-count") {
        return { unread: 2 };
      }
      if (path.startsWith("/api/v1/notifications?")) {
        return {
          items: [
            {
              id: "notice-1",
              category: "announcement",
              priority: "high",
              title: "Members-only notice",
              body: "<p>Official update</p>",
              deep_link: null,
              read_at: null,
              created_at: new Date().toISOString(),
            },
          ],
        };
      }
      throw new Error(`Unhandled test request: ${path}`);
    });
  });

  it("opens a dropdown of unread notifications with a view-all link", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <NotificationBell enabled />
      </QueryClientProvider>,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Notifications" }),
    );

    expect(
      await screen.findByRole("dialog", {
        name: "Recent unread notifications",
      }),
    ).toBeTruthy();
    expect(await screen.findByText("Members-only notice")).toBeTruthy();
    expect(screen.getByText(/Official announcement/)).toBeTruthy();
    const viewAll = screen.getByRole("link", {
      name: "View all notifications",
    });
    expect(viewAll.getAttribute("href")).toBe("/dashboard/notifications");
  });

  it("marks a notification read when opened from the dropdown", async () => {
    mockedApi.mockImplementation(async (path, options) => {
      if (path === "/api/v1/notifications/unread-count") {
        return { unread: 1 };
      }
      if (path.startsWith("/api/v1/notifications?")) {
        return {
          items: [
            {
              id: "notice-2",
              category: "direct",
              priority: "normal",
              title: "Direct alert",
              body: "<p>Hello</p>",
              deep_link: "/dashboard/events",
              read_at: null,
              created_at: new Date().toISOString(),
            },
          ],
        };
      }
      if (path === "/api/v1/notifications/notice-2/read") {
        expect(options?.method).toBe("POST");
        return { message: "ok" };
      }
      throw new Error(`Unhandled test request: ${path}`);
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <NotificationBell enabled />
      </QueryClientProvider>,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Notifications" }),
    );
    fireEvent.click(await screen.findByRole("link", { name: /Direct alert/ }));

    await waitFor(() =>
      expect(
        mockedApi.mock.calls.some(
          ([path, options]) =>
            path === "/api/v1/notifications/notice-2/read" &&
            options?.method === "POST",
        ),
      ).toBe(true),
    );
  });
});
