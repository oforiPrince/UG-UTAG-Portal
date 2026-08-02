import Link from "next/link";

export function PageHero({
  eyebrow,
  title,
  intro,
}: {
  eyebrow: string;
  title: string;
  intro: string;
}) {
  return (
    <section className="relative isolate w-full overflow-hidden bg-[#122b48] text-white">
      <div
        className="absolute inset-0 -z-20 bg-cover bg-center"
        style={{ backgroundImage: "url('/brand/campus-main.jpg')" }}
      />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(13,39,67,.96)_0%,rgba(13,39,67,.86)_45%,rgba(13,39,67,.46)_100%)]" />
      <div className="mx-auto w-full min-w-0 max-w-[82rem] px-4 py-12 sm:px-6 sm:py-18 lg:px-8 lg:py-20">
        <nav
          aria-label="Breadcrumb"
          className="flex min-w-0 flex-wrap items-center gap-2 text-[.68rem] font-bold tracking-wide text-white/62 uppercase"
        >
          <Link href="/" className="hover:text-white">
            Home
          </Link>
          <span aria-hidden="true">/</span>
          <span className="min-w-0 break-words text-gold">{eyebrow}</span>
        </nav>
        <h1 className="display-type mt-4 max-w-4xl text-[1.85rem] leading-[1.12] break-words text-white sm:mt-5 sm:text-5xl sm:leading-[1.08] lg:text-6xl">
          {title}
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 break-words text-white/75 sm:mt-5 sm:text-base">
          {intro}
        </p>
      </div>
      <div className="h-1 bg-gold" />
    </section>
  );
}
