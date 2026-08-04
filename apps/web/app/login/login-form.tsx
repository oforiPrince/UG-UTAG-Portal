"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Eye, EyeOff, LoaderCircle, LogIn } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  defaultDeliveryCapabilities,
  deliveryAvailable,
  type DeliveryCapabilities,
} from "@/lib/delivery-capabilities";

const schema = z.object({ email: z.email(), password: z.string().min(1) });
type Values = z.infer<typeof schema>;
type AuthResponse = {
  user: {
    must_change_password: boolean;
    must_complete_executive_profile: boolean;
  };
};
const input =
  "min-h-12 w-full rounded-xl border border-line bg-panel px-4 text-sm outline-none transition focus:border-ink/25";

export function LoginForm() {
  const [show, setShow] = useState(false);
  const router = useRouter();
  const search = useSearchParams();
  const capabilities = useQuery({
    queryKey: ["public", "capabilities"],
    queryFn: () =>
      api<DeliveryCapabilities>("/api/v1/public/capabilities"),
    staleTime: 60_000,
    placeholderData: defaultDeliveryCapabilities,
  });
  const showForgotPassword =
    capabilities.isSuccess &&
    deliveryAvailable(capabilities.data ?? defaultDeliveryCapabilities);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });
  const submit = handleSubmit(async (values) => {
    try {
      const session = await api<AuthResponse>("/api/v1/auth/login", {
        method: "POST",
        body: values,
      });
      toast.success("Welcome!!!");
      const next = search.get("next");
      const destination = session.user.must_change_password
        ? "/dashboard/profile?password=required"
        : session.user.must_complete_executive_profile
          ? "/dashboard/profile?executive=required"
          : next?.startsWith("/dashboard")
            ? next
            : "/dashboard";
      router.replace(destination);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Sign in failed");
    }
  });
  return (
    <form className="grid gap-5" onSubmit={submit}>
      <label className="grid gap-2 text-xs font-bold">
        University or member email
        <input
          className={input}
          type="email"
          autoComplete="email"
          {...register("email")}
        />
        {errors.email && (
          <span className="text-red-600">Enter a valid email</span>
        )}
      </label>
      <label className="grid gap-2 text-xs font-bold">
        <span className="flex justify-between">
          Password
          {showForgotPassword ? (
            <Link
              className="font-semibold text-coral"
              href="/forgot-password"
            >
              Forgot password?
            </Link>
          ) : null}
        </span>
        <span className="relative">
          <input
            className={`${input} pr-12`}
            type={show ? "text" : "password"}
            autoComplete="current-password"
            {...register("password")}
          />
          <button
            type="button"
            onClick={() => setShow((value) => !value)}
            className="absolute top-1/2 right-3 -translate-y-1/2 p-2 text-muted"
            aria-label={show ? "Hide password" : "Show password"}
          >
            {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </span>
        {errors.password && (
          <span className="text-red-600">Enter your password</span>
        )}
      </label>
      <Button className="mt-2 w-full" type="submit" disabled={isSubmitting}>
        {isSubmitting ? (
          <LoaderCircle className="size-4 animate-spin" />
        ) : (
          <LogIn className="size-4" />
        )}{" "}
        Sign in securely
      </Button>
      <p className="text-center text-xs leading-6 text-muted">
        Need access? Contact the UG UTAG secretariat. Accounts are issued to
        verified members.
      </p>
    </form>
  );
}
