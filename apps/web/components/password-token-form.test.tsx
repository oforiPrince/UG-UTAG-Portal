import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { PasswordTokenForm } from "./password-token-form";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/api", () => ({ api: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));

describe("password token form", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/reset-password");
  });

  it("reads a fragment token, removes it from the URL, and resets the password", async () => {
    const token = "secure-reset-token-" + "a".repeat(40);
    window.history.replaceState({}, "", `/reset-password#token=${token}`);
    vi.mocked(api).mockResolvedValue({ message: "Password reset" });

    render(
      <PasswordTokenForm
        endpoint="/api/v1/auth/reset-password"
        action="Reset password"
        successMessage="Your password has been reset"
        successRedirect="/login?reset=success"
      />,
    );

    const password = await screen.findByLabelText("New password");
    await waitFor(() => expect(window.location.hash).toBe(""));
    fireEvent.change(password, { target: { value: "NewPassword456" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "DifferentPassword789" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Reset password" }).closest("form")!,
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "The two passwords do not match",
    );
    expect(api).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "NewPassword456" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Reset password" }).closest("form")!,
    );

    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/api/v1/auth/reset-password", {
        method: "POST",
        body: { token, password: "NewPassword456" },
      }),
    );
    expect(replace).toHaveBeenCalledWith("/login?reset=success");
  });

  it("shows a recovery action when the secure token is missing", async () => {
    render(
      <PasswordTokenForm
        endpoint="/api/v1/auth/reset-password"
        action="Reset password"
        successMessage="Your password has been reset"
        invalidLinkHref="/forgot-password"
        invalidLinkLabel="Request a new reset link"
      />,
    );

    expect(await screen.findByText("Secure link required")).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "Request a new reset link" })
        .getAttribute("href"),
    ).toBe("/forgot-password");
  });
});
