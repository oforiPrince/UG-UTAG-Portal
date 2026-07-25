import { Suspense } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordTokenForm } from "@/components/password-token-form";
export default function ResetPage() { return <AuthShell title="Choose a new password." intro="This secure link expires after 30 minutes and can only be used once."><Suspense><PasswordTokenForm endpoint="/api/v1/auth/reset-password" action="Reset password" /></Suspense></AuthShell>; }
