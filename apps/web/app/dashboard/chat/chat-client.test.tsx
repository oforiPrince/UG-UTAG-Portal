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

import { ChatClient } from "./chat-client";

vi.mock("@/lib/api", () => ({ api: vi.fn() }));

const mockedApi = vi.mocked(api);
const now = "2026-08-30T12:00:00Z";

function conversation(isMuted = false) {
  return {
    id: "conversation-1",
    title: null,
    kind: "direct",
    created_by_id: "user-me",
    member_count: 2,
    unread_count: 1,
    last_message_at: now,
    display_title: "Dr. Ama Mensah",
    direct_member_id: "user-ama",
    current_user_role: "owner",
    is_muted: isMuted,
    last_message_preview: "I have reviewed the agenda",
    last_message_sender: "Dr. Ama Mensah",
    created_at: now,
  };
}

describe("ChatClient", () => {
  let ownMessage = "Here is the draft agenda";

  beforeEach(() => {
    ownMessage = "Here is the draft agenda";
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: true,
        media: "(min-width: 1024px)",
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    HTMLElement.prototype.scrollIntoView = vi.fn();
    mockedApi.mockReset();
    mockedApi.mockImplementation(async (path, options) => {
      if (path === "/api/v1/auth/me") {
        return { id: "user-me", full_name: "Prof. Portal Admin" };
      }
      if (path === "/api/v1/chat/conversations") {
        return [conversation()];
      }
      if (
        path.startsWith("/api/v1/chat/conversations/conversation-1/messages")
      ) {
        return {
          items: [
            {
              id: "message-1",
              conversation_id: "conversation-1",
              sender_id: "user-me",
              sender_name: "Prof. Portal Admin",
              text: ownMessage,
              created_at: now,
              edited_at: ownMessage.includes("final") ? now : null,
              client_message_id: "client-message-1",
              reply_to_id: null,
              reply_to: null,
              read_by: 1,
              attachments: [],
            },
            {
              id: "message-2",
              conversation_id: "conversation-1",
              sender_id: "user-ama",
              sender_name: "Dr. Ama Mensah",
              text: "I have reviewed the agenda",
              created_at: "2026-08-30T12:01:00Z",
              edited_at: null,
              client_message_id: "client-message-2",
              reply_to_id: "message-1",
              reply_to: {
                id: "message-1",
                sender_id: "user-me",
                sender_name: "Prof. Portal Admin",
                text: ownMessage,
              },
              read_by: 0,
              attachments: [],
            },
          ],
          page: 1,
          page_size: 50,
          total: 2,
          pages: 1,
        };
      }
      if (path === "/api/v1/chat/conversations/conversation-1/read") {
        return { message: "Conversation marked as read" };
      }
      if (
        path === "/api/v1/chat/messages/message-1" &&
        options?.method === "PATCH"
      ) {
        ownMessage = (options.body as { text: string }).text;
        return {};
      }
      if (
        path === "/api/v1/chat/conversations/conversation-1/preferences" &&
        options?.method === "PATCH"
      ) {
        return conversation(true);
      }
      throw new Error(`Unhandled test request: ${path}`);
    });
  });

  afterEach(() => cleanup());

  it("renders direct-chat identity, previews, reply context, and connection state", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ChatClient />
      </QueryClientProvider>,
    );

    expect(
      (await screen.findAllByText("Dr. Ama Mensah")).length,
    ).toBeGreaterThan(0);
    expect(await screen.findByText("I have reviewed the agenda")).toBeTruthy();
    expect(screen.getByText(/Offline — messages will sync/)).toBeTruthy();
    expect(screen.getByText("Prof. Portal Admin")).toBeTruthy();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Reply to message" })[1]!,
    );
    expect(screen.getByText("Replying to Dr. Ama Mensah")).toBeTruthy();
    expect(
      screen
        .getByRole("textbox", { name: "Message" })
        .getAttribute("placeholder"),
    ).toBe("Reply to Dr. Ama Mensah");
    expect(
      screen.getByRole("textbox", { name: "Message" }).closest("form")
        ?.className,
    ).toContain("pb-[calc(6rem+env(safe-area-inset-bottom))]");
  });

  it("edits an owned message and updates mute preferences", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ChatClient />
      </QueryClientProvider>,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Edit message" }),
    );
    const editor = screen.getByRole("textbox", { name: "Edit message" });
    expect(editor.style.color).toBe("var(--paper)");
    expect(editor.style.caretColor).toBe("var(--paper)");
    fireEvent.change(editor, {
      target: { value: "Here is the final agenda" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(
        mockedApi.mock.calls.some(
          ([path, options]) =>
            path === "/api/v1/chat/messages/message-1" &&
            options?.method === "PATCH" &&
            (options.body as { text: string }).text ===
              "Here is the final agenda",
        ),
      ).toBe(true),
    );

    fireEvent.click(screen.getByRole("button", { name: "Mute conversation" }));
    await waitFor(() =>
      expect(
        mockedApi.mock.calls.some(
          ([path, options]) =>
            path === "/api/v1/chat/conversations/conversation-1/preferences" &&
            options?.method === "PATCH",
        ),
      ).toBe(true),
    );
    expect(
      await screen.findByRole("button", { name: "Unmute conversation" }),
    ).toBeTruthy();
  });
});
