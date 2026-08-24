import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell } from "@/components/auth-shell";
import { PasswordTokenForm } from "@/components/password-token-form";

export const metadata: Metadata = { title: "Reset password" };

export default function ResetPage() {
  return (
    <AuthShell
      title="Choose a new password."
      intro="This secure link expires after 30 minutes and can only be used once. Completing the reset signs your account out on every device."
    >
      <Suspense>
        <PasswordTokenForm
          endpoint="/api/v1/auth/reset-password"
          action="Reset password"
          successMessage="Your password has been reset"
          successRedirect="/login?reset=success"
          invalidLinkHref="/forgot-password"
          invalidLinkLabel="Request a new reset link"
        />
      </Suspense>
    </AuthShell>
  );
}
