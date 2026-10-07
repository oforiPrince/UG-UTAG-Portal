import { redirect } from "next/navigation";

import { AuthShell } from "@/components/auth-shell";
import {
  deliveryAvailable,
  getDeliveryCapabilities,
} from "@/lib/delivery-capabilities";

import { ForgotForm } from "./forgot-form";

export default async function ForgotPage() {
  const capabilities = await getDeliveryCapabilities();
  if (!deliveryAvailable(capabilities)) {
    redirect("/login");
  }
  return (
    <AuthShell
      title="Reset access."
      intro="Enter your member email. For privacy, the response is the same whether or not an account exists."
    >
      <ForgotForm />
    </AuthShell>
  );
}
