import { cn } from "@/lib/utils";

export function PublicEmptyState({
  title,
  description,
  inverse = false,
  className,
}: {
  title: string;
  description: string;
  inverse?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "col-span-full rounded-md border border-dashed px-6 py-10 text-center",
        inverse
          ? "border-white/25 bg-white/6"
          : "border-[#b9c8d7] bg-[#f7f9fc]",
        className,
      )}
    >
      <span className="mx-auto block h-1 w-12 bg-gold" />
      <h3
        className={cn(
          "mt-5 text-lg font-extrabold",
          inverse ? "text-white" : "text-[#172f4d]",
        )}
      >
        {title}
      </h3>
      <p
        className={cn(
          "mx-auto mt-2 max-w-xl text-sm leading-6",
          inverse ? "text-white/68" : "text-muted",
        )}
      >
        {description}
      </p>
    </div>
  );
}
