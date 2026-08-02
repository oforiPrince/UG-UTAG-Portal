import Image from "next/image";
import Link from "next/link";

export function Logo({
  inverse = false,
  compact = false,
}: {
  inverse?: boolean;
  compact?: boolean;
}) {
  return (
    <Link
      href="/"
      className="inline-flex shrink-0 items-center"
      aria-label="UG UTAG home"
    >
      <Image
        src={`/brand/${inverse ? "logo-white.png" : "logo-blue.png"}`}
        alt="University Teachers Association of Ghana, University of Ghana Branch"
        width={1128}
        height={227}
        priority
        unoptimized
        className={
          compact
            ? "h-10 w-auto max-w-[12rem] object-contain"
            : "h-11 w-auto max-w-[13rem] object-contain sm:h-13 sm:max-w-[14rem]"
        }
      />
    </Link>
  );
}
