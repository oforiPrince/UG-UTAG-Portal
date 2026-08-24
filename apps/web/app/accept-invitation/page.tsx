import { Suspense } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordTokenForm } from "@/components/password-token-form";

export default function InvitationPage() {
  return (
    <AuthShell
      title="Activate your account."
      intro="Set a strong password to complete your verified UG UTAG member profile."
    >
      <Suspense>
        <PasswordTokenForm
          endpoint="/api/v1/auth/accept-invitation"
          action="Activate account"
          successMessage="Your account has been activated"
        />
      </Suspense>
    </AuthShell>
  );
}
