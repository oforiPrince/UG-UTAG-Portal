import { AuthShell } from "@/components/auth-shell";
import { ForgotForm } from "./forgot-form";
export default function ForgotPage() { return <AuthShell title="Reset access." intro="Enter your member email. For privacy, the response is the same whether or not an account exists."><ForgotForm /></AuthShell>; }
