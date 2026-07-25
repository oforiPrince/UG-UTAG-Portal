"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, Send } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const schema = z.object({
  name: z.string().min(2),
  email: z.email(),
  subject: z.string().min(3),
  message: z.string().min(10),
  website: z.string().optional(),
});
type ContactData = z.infer<typeof schema>;

const input =
  "min-h-12 w-full rounded-md border border-line bg-white px-4 text-sm outline-none transition focus:border-sky focus:ring-2 focus:ring-sky/15";

export function ContactForm() {
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
  return (
    <form
      onSubmit={submit}
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
        <input className={input} {...register("name")} />
        {errors.name && <span className="text-red-600">Enter your name</span>}
      </label>
      <label className="grid gap-2 text-xs font-bold text-[#2d4056]">
        Email
        <input className={input} type="email" {...register("email")} />
        {errors.email && (
          <span className="text-red-600">Enter a valid email</span>
        )}
      </label>
      <label className="grid gap-2 text-xs font-bold text-[#2d4056] sm:col-span-2">
        Subject
        <input className={input} {...register("subject")} />
      </label>
      <label className="grid gap-2 text-xs font-bold text-[#2d4056] sm:col-span-2">
        Message
        <textarea
          className={`${input} min-h-40 py-4`}
          {...register("message")}
        />
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
