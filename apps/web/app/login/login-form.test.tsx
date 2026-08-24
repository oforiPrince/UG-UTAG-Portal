import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { LoginForm } from "./login-form";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/api", () => ({ api: vi.fn() }));

function renderLogin() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <LoginForm />
    </QueryClientProvider>,
  );
}

describe("login password recovery", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(cleanup);

  it("shows forgot password when SMTP email delivery is configured", async () => {
    vi.mocked(api).mockResolvedValue({
      email_delivery: true,
      sms_delivery: false,
    });

    renderLogin();

    const recovery = await screen.findByRole("link", {
      name: "Forgot password?",
    });
    expect(recovery.getAttribute("href")).toBe("/forgot-password");
  });

  it("keeps recovery hidden until email delivery is configured", async () => {
    vi.mocked(api).mockResolvedValue({
      email_delivery: false,
      sms_delivery: true,
    });

    renderLogin();

    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: "Forgot password?" })).toBeNull();
  });
});
