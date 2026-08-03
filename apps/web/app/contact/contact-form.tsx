"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Send } from "lucide-react";
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

const schema = z.object({
  name: z.string().trim().min(2, "Enter your name"),
  email: z.email("Enter a valid email address"),
  subject: z
    .string()
    .trim()
    .min(3, "Enter a subject using at least 3 characters"),
  message: z
    .string()
    .trim()
    .min(10, "Enter a message using at least 10 characters"),
  website: z.string().optional(),
});
type ContactData = z.infer<typeof schema>;

const input =
  "min-h-12 w-full rounded-md border border-line bg-white px-4 text-sm outline-none transition focus:border-ink/25 focus:ring-0";

export function ContactForm() {
  const capabilities = useQuery({
    queryKey: ["public", "capabilities"],
    queryFn: () =>
      api<DeliveryCapabilities>("/api/v1/public/capabilities"),
    staleTime: 60_000,
    placeholderData: defaultDeliveryCapabilities,
  });
  const canSend = deliveryAvailable(
    capabilities.data ?? defaultDeliveryCapabilities,
  );
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ContactData>({
    resolver: zodResolver(schema),
    defaultValues: { website: "" },
  });
  const submit = handleSubmit(async (values) => {
    try {
      await api("/api/v1/public/contact", { method: "POST", body: values });
      toast.success("Your message has been received");
      reset();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not send the message",
      );
    }
  });

  if (capabilities.isPending) {
    return (
      <div className="rounded-md border border-line bg-panel p-6 sm:p-8">
        <p className="text-sm text-[#2d4056]">Checking contact availability…</p>
      </div>
    );
  }

  if (capabilities.isSuccess && !canSend) {
    return (
      <div className="rounded-md border border-line bg-panel p-6 shadow-[0_10px_32px_rgb(23_43_69_/_8%)] sm:p-8">
        <p className="text-[.7rem] font-extrabold tracking-[.14em] text-coral uppercase">
          Send a message
        </p>
        <h2 className="mt-2 text-2xl font-extrabold text-[#172f4d]">
          Contact form unavailable
        </h2>
        <p className="mt-3 text-sm leading-6 text-[#2d4056]">
          Online messages are temporarily unavailable. Please use the
          secretariat phone or email listed on this page.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      className="grid gap-5 rounded-md border border-line bg-panel p-6 shadow-[0_10px_32px_rgb(23_43_69_/_8%)] sm:grid-cols-2 sm:p-8"
    >
      <div className="sm:col-span-2">
        <p className="text-[.7rem] font-extrabold tracking-[.14em] text-coral uppercase">
          Send a message
        </p>
        <h2 className="mt-2 text-2xl font-extrabold text-[#172f4d]">
          How can we assist?
        </h2>
      </div>
      <label className="grid gap-2 text-xs font-bold text-[#2d4056]">
        Name
        <input
          className={input}
          autoComplete="name"
          aria-invalid={Boolean(errors.name)}
          aria-describedby={errors.name ? "contact-name-error" : undefined}
          {...register("name")}
        />
        {errors.name && (
          <span id="contact-name-error" role="alert" className="text-red-600">
            {errors.name.message}
          </span>
        )}
      </label>
      <label className="grid gap-2 text-xs font-bold text-[#2d4056]">
        Email
        <input
          className={input}
          type="email"
          autoComplete="email"
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? "contact-email-error" : undefined}
          {...register("email")}
        />
        {errors.email && (
          <span id="contact-email-error" role="alert" className="text-red-600">
            {errors.email.message}
          </span>
        )}
      </label>
      <label className="grid gap-2 text-xs font-bold text-[#2d4056] sm:col-span-2">
        Subject
        <input
          className={input}
          aria-invalid={Boolean(errors.subject)}
          aria-describedby={
            errors.subject ? "contact-subject-error" : undefined
          }
          {...register("subject")}
        />
        {errors.subject && (
          <span
            id="contact-subject-error"
            role="alert"
            className="text-red-600"
          >
            {errors.subject.message}
          </span>
        )}
      </label>
      <label className="grid gap-2 text-xs font-bold text-[#2d4056] sm:col-span-2">
        Message
        <textarea
          className={`${input} min-h-40 py-4`}
          aria-invalid={Boolean(errors.message)}
          aria-describedby={
            errors.message ? "contact-message-error" : undefined
          }
          {...register("message")}
        />
        {errors.message && (
          <span
            id="contact-message-error"
            role="alert"
            className="text-red-600"
          >
            {errors.message.message}
          </span>
        )}
      </label>
      <input
        className="hidden"
        tabIndex={-1}
        autoComplete="off"
        {...register("website")}
      />
      <div className="sm:col-span-2">
        <Button className="rounded-md" type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <Send className="size-4" />
          )}{" "}
          Send message
        </Button>
      </div>
    </form>
  );
}
