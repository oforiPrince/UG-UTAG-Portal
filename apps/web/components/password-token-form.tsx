"use client";

import { LoaderCircle, LockKeyhole } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function PasswordTokenForm({ endpoint, action }: { endpoint: string; action: string }) {
  const search = useSearchParams();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  async function submit(event: React.FormEvent) { event.preventDefault(); if (password !== confirm) { toast.error("Passwords do not match"); return; } const token = search.get("token"); if (!token) { toast.error("This link is incomplete"); return; } setLoading(true); try { await api(endpoint, { method: "POST", body: { token, password } }); toast.success(action); router.replace("/login"); } catch (error) { toast.error(error instanceof Error ? error.message : "Could not update password"); } finally { setLoading(false); } }
  const style = "min-h-12 rounded-xl border border-line bg-panel px-4 text-sm outline-none focus:border-ink/25";
  return <form onSubmit={submit} className="grid gap-5"><label className="grid gap-2 text-xs font-bold">New password<input className={style} type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} /></label><label className="grid gap-2 text-xs font-bold">Confirm password<input className={style} type="password" minLength={8} value={confirm} onChange={(event) => setConfirm(event.target.value)} /></label><p className="text-xs leading-5 text-muted">Use 8 or more characters with upper and lowercase letters and a number.</p><Button disabled={loading}>{loading ? <LoaderCircle className="size-4 animate-spin" /> : <LockKeyhole className="size-4" />} {action}</Button></form>;
}
