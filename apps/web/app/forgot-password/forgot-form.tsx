"use client";

import { LoaderCircle, Mail } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function ForgotForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await api("/api/v1/auth/forgot-password", {
        method: "POST",
        body: { email },
      });
      setSent(true);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not submit request",
      );
    } finally {
      setLoading(false);
    }
  }
  if (sent)
    return (
      <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/8 p-6">
        <Mail className="size-6 text-emerald-600 dark:text-emerald-300" />
        <h2 className="mt-5 text-lg font-black">Check your inbox</h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          If that email belongs to an active account, a secure reset link is on
          its way.
        </p>
      </div>
    );
  return (
    <form onSubmit={submit} className="grid gap-5">
      <label className="grid gap-2 text-xs font-bold">
        Member email
        <input
          required
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="min-h-12 rounded-xl border border-line bg-panel px-4 text-sm outline-none focus:border-ink/25"
        />
      </label>
      <Button disabled={loading} className="w-full">
        {loading ? (
          <LoaderCircle className="size-4 animate-spin" />
        ) : (
          <Mail className="size-4" />
        )}{" "}
        Send reset link
      </Button>
    </form>
  );
}
