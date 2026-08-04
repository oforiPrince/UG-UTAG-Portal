import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell } from "@/components/auth-shell";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Member sign in" };
export default function LoginPage() { return <AuthShell title="Welcome!!!" intro="Sign in to your live member dashboard, documents, events and association communications."><Suspense><LoginForm /></Suspense></AuthShell>; }
