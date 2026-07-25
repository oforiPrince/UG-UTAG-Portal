import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-bold transition-all disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-ink text-paper shadow-[0_10px_30px_rgba(12,25,48,.18)] hover:-translate-y-0.5 hover:bg-[#183052]",
        gold: "bg-gold text-[#172035] shadow-[0_10px_30px_rgba(213,168,42,.24)] hover:-translate-y-0.5 hover:brightness-105",
        outline: "border border-line bg-panel/65 text-ink hover:border-ink/30 hover:bg-panel",
        ghost: "text-ink hover:bg-ink/6",
        danger: "bg-red-600 text-white hover:bg-red-700",
      },
      size: {
        default: "h-11 px-5",
        sm: "h-9 min-h-9 px-4 text-xs",
        icon: "size-11 p-0",
      },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean };

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
