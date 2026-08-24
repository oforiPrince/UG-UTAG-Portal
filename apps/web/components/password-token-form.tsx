"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type PasswordTokenFormProps = {
  endpoint: string;
  action: string;
  successMessage: string;
  successRedirect?: string;
  invalidLinkHref?: string;
  invalidLinkLabel?: string;
};

const inputStyle =
  "min-h-12 w-full rounded-xl border border-line bg-panel px-4 pr-12 text-sm outline-none transition focus:border-ink/25";

export function PasswordTokenForm({
  endpoint,
  action,
  successMessage,
  successRedirect = "/login",
  invalidLinkHref = "/login",
  invalidLinkLabel = "Back to sign in",
}: PasswordTokenFormProps) {
  const search = useSearchParams();
  const router = useRouter();
  const queryToken = search.get("token") ?? "";
  const [token, setToken] = useState(queryToken);
  const [tokenReady, setTokenReady] = useState(Boolean(queryToken));
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const synchronizeToken = () => {
      if (!active) return;
      const fragmentToken = new URLSearchParams(
        window.location.hash.slice(1),
      ).get("token");
      const resolvedToken = fragmentToken ?? queryToken;
      setToken(resolvedToken);
      setTokenReady(true);

      if (resolvedToken && (window.location.search || window.location.hash)) {
        window.history.replaceState(
          window.history.state,
          "",
          window.location.pathname,
        );
      }
    };

    window.addEventListener("hashchange", synchronizeToken);
    queueMicrotask(synchronizeToken);
    return () => {
      active = false;
      window.removeEventListener("hashchange", synchronizeToken);
    };
  }, [queryToken]);

  const requirements = [
    { label: "At least 8 characters", met: password.length >= 8 },
    { label: "One uppercase letter", met: /[A-Z]/.test(password) },
    { label: "One lowercase letter", met: /[a-z]/.test(password) },
    { label: "One number", met: /\d/.test(password) },
  ];
  const passwordsMatch = confirm.length === 0 || password === confirm;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError(
        "This secure link is incomplete. Request a new one and try again.",
      );
      return;
    }
    if (requirements.some((requirement) => !requirement.met)) {
      setError("Your new password does not yet meet all the requirements.");
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await api(endpoint, { method: "POST", body: { token, password } });
      toast.success(successMessage);
      router.replace(successRedirect);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Could not update your password",
      );
    } finally {
      setLoading(false);
    }
  }

  if (!tokenReady) {
    return (
      <div
        className="flex min-h-28 items-center justify-center gap-3 text-sm text-muted"
        role="status"
      >
        <LoaderCircle className="size-4 animate-spin" /> Preparing your secure
        link…
      </div>
    );
  }

  if (!token) {
    return (
      <div className="grid gap-6">
        <div
          className="rounded-2xl border border-amber-500/25 bg-amber-500/8 p-6"
          role="alert"
        >
          <LockKeyhole className="size-6 text-amber-700 dark:text-amber-300" />
          <h2 className="mt-5 text-lg font-black">Secure link required</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            This link is incomplete. Open the latest message sent by the portal
            or request a new link.
          </p>
        </div>
        <Link
          href={invalidLinkHref}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full text-sm font-bold text-ink hover:bg-ink/6"
        >
          <ArrowLeft className="size-4" /> {invalidLinkLabel}
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-5" aria-busy={loading}>
      <label className="grid gap-2 text-xs font-bold" htmlFor="new-password">
        New password
      </label>
      <div className="relative -mt-3">
        <input
          id="new-password"
          className={inputStyle}
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          minLength={8}
          maxLength={256}
          required
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            setError(null);
          }}
          aria-describedby="password-requirements"
        />
        <button
          type="button"
          onClick={() => setShowPassword((visible) => !visible)}
          className="absolute top-1/2 right-3 -translate-y-1/2 rounded-lg p-2 text-muted hover:bg-ink/6 hover:text-ink"
          aria-label={showPassword ? "Hide new password" : "Show new password"}
        >
          {showPassword ? (
            <EyeOff className="size-4" />
          ) : (
            <Eye className="size-4" />
          )}
        </button>
      </div>

      <div
        id="password-requirements"
        className="grid grid-cols-1 gap-2 rounded-2xl border border-line bg-panel/65 p-4 text-xs sm:grid-cols-2"
      >
        {requirements.map((requirement) => (
          <span
            key={requirement.label}
            className={
              requirement.met
                ? "flex items-center gap-2 text-emerald-700 dark:text-emerald-300"
                : "flex items-center gap-2 text-muted"
            }
          >
            {requirement.met ? (
              <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <Circle className="size-4 shrink-0" aria-hidden="true" />
            )}
            {requirement.label}
          </span>
        ))}
      </div>

      <label
        className="grid gap-2 text-xs font-bold"
        htmlFor="confirm-password"
      >
        Confirm new password
      </label>
      <div className="relative -mt-3">
        <input
          id="confirm-password"
          className={inputStyle}
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          minLength={8}
          maxLength={256}
          required
          value={confirm}
          onChange={(event) => {
            setConfirm(event.target.value);
            setError(null);
          }}
          aria-invalid={!passwordsMatch}
          aria-describedby={
            !passwordsMatch ? "password-match-error" : undefined
          }
        />
      </div>
      {!passwordsMatch ? (
        <p
          id="password-match-error"
          className="-mt-3 text-xs font-semibold text-red-600 dark:text-red-300"
        >
          The two passwords do not match.
        </p>
      ) : null}

      {error ? (
        <p
          className="rounded-xl border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-700 dark:text-red-200"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <Button disabled={loading} type="submit" className="w-full">
        {loading ? (
          <LoaderCircle className="size-4 animate-spin" />
        ) : (
          <LockKeyhole className="size-4" />
        )}{" "}
        {action}
      </Button>
    </form>
  );
}
