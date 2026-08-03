"use client";

import {
  ArrowUpRight,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  ExternalLink,
  Mail,
  Phone,
  UserRound,
  X,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";

import type { PublicExecutiveProfile } from "@/lib/leadership";
import { publicMediaUrl } from "@/lib/public-media";
import { cn, formatPersonName, formatRankForName, humanize, initials } from "@/lib/utils";

type ExecutiveProfileButtonProps = {
  profile: PublicExecutiveProfile;
  className?: string;
};

const SOCIAL_LINK_LABELS: Record<string, string> = {
  facebook: "Facebook",
  linkedin: "LinkedIn",
  twitter: "X / Twitter",
  x: "X / Twitter",
  website: "Personal website",
  personal_website: "Personal website",
};

function safeExternalUrl(value: string) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : null;
  } catch {
    return null;
  }
}

function formatAppointmentDate(value: string | null) {
  if (!value) return "Not provided";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "Not provided";
  return new Intl.DateTimeFormat("en-GH", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function ExecutiveProfileModal({
  profile,
  onDismiss,
}: {
  profile: PublicExecutiveProfile;
  onDismiss: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const affiliation = [
    profile.department_name,
    profile.school_name,
    profile.college_name,
  ].filter((value): value is string => Boolean(value));
  const socialLinks = Object.entries(profile.social_links)
    .map(([name, value]) => ({
      name: SOCIAL_LINK_LABELS[name.toLowerCase()] ?? humanize(name),
      url: safeExternalUrl(value),
    }))
    .filter((link): link is { name: string; url: string } => link.url !== null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.showModal();
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (dialog.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="m-auto max-h-[calc(100dvh-1.5rem)] w-[min(64rem,calc(100%-1.5rem))] overflow-hidden rounded-2xl bg-white p-0 text-left text-[#172b45] shadow-[0_30px_100px_rgb(5_18_35_/_38%)] backdrop:bg-[#07182c]/72 backdrop:backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) dialogRef.current?.close();
      }}
      onClose={onDismiss}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          dialogRef.current?.close();
        }
      }}
    >
      <div className="grid max-h-[calc(100dvh-1.5rem)] overflow-y-auto md:grid-cols-[19rem_1fr] md:overflow-hidden">
        <aside className="relative overflow-hidden bg-[#172f4d] px-7 py-9 text-white md:flex md:min-h-[36rem] md:flex-col md:px-8 md:py-10">
          <div className="absolute inset-x-0 top-0 h-1.5 bg-gold" />
          <div className="absolute -top-20 -right-20 size-60 rounded-full border border-white/8" />
          <div className="absolute -top-8 -right-8 size-36 rounded-full border border-white/8" />
          <div className="relative">
            {profile.profile_media_id ? (
              <Image
                alt={profile.full_name}
                className="size-28 rounded-full border-4 border-white/18 object-cover shadow-xl md:size-36"
                height={144}
                src={publicMediaUrl(profile.profile_media_id, "w480")!}
                unoptimized
                width={144}
              />
            ) : (
              <span className="grid size-28 place-items-center rounded-full border-4 border-white/18 bg-white/10 text-3xl font-black text-gold shadow-xl md:size-36 md:text-4xl">
                {initials(profile.full_name)}
              </span>
            )}
            <p className="mt-7 text-[.68rem] font-extrabold tracking-[.14em] text-gold uppercase">
              {profile.is_acting ? "Acting " : ""}
              {profile.position}
            </p>
            {profile.portfolio ? (
              <p className="mt-3 text-sm leading-6 text-white/72">
                {profile.portfolio}
              </p>
            ) : null}
          </div>

          <div className="relative mt-8 space-y-3 border-t border-white/12 pt-6 md:mt-auto">
            <a
              className="flex min-h-11 items-center gap-3 rounded-lg px-2 text-sm text-white/82 transition hover:bg-white/8 hover:text-white"
              href={`mailto:${profile.email}`}
            >
              <Mail aria-hidden="true" className="size-4 shrink-0 text-gold" />
              <span className="min-w-0 break-all">{profile.email}</span>
            </a>
            {profile.phone_number ? (
              <a
                className="flex min-h-11 items-center gap-3 rounded-lg px-2 text-sm text-white/82 transition hover:bg-white/8 hover:text-white"
                href={`tel:${profile.phone_number.replace(/[^\d+]/g, "")}`}
              >
                <Phone
                  aria-hidden="true"
                  className="size-4 shrink-0 text-gold"
                />
                {profile.phone_number}
              </a>
            ) : null}
          </div>
        </aside>

        <div className="relative p-6 sm:p-8 md:max-h-[calc(100dvh-1.5rem)] md:overflow-y-auto md:p-10">
          <button
            ref={closeButtonRef}
            aria-label={`Close ${profile.full_name}'s profile`}
            className="absolute top-4 right-4 grid size-11 place-items-center rounded-full border border-line bg-white text-[#172f4d] transition hover:border-[#172f4d]/30 hover:bg-[#f5f8fb]"
            onClick={() => dialogRef.current?.close()}
            type="button"
          >
            <X aria-hidden="true" className="size-5" />
          </button>

          <div className="border-b border-line pr-12 pb-7">
            <p className="text-[.68rem] font-extrabold tracking-[.14em] text-coral uppercase">
              Executive profile
            </p>
            <h2
              className="display-type mt-2 text-3xl text-[#172f4d] sm:text-4xl"
              id={titleId}
            >
              {formatPersonName(profile.full_name)}
            </h2>
            <p className="mt-2 font-bold text-coral">{profile.position}</p>
            {profile.summary ? (
              <p
                className="mt-5 max-w-2xl text-sm leading-7 text-muted"
                id={descriptionId}
              >
                {profile.summary}
              </p>
            ) : (
              <span className="sr-only" id={descriptionId}>
                Complete public executive profile
              </span>
            )}
          </div>

          <section aria-labelledby={`${titleId}-about`} className="pt-7">
            <h3
              className="flex items-center gap-2 text-sm font-extrabold tracking-wide text-[#172f4d] uppercase"
              id={`${titleId}-about`}
            >
              <UserRound aria-hidden="true" className="size-4 text-coral" />
              About
            </h3>
            {profile.biography_html ? (
              <div
                className="mt-4 text-sm leading-7 text-muted [&_a]:font-bold [&_a]:text-coral [&_a]:underline [&_li]:ml-5 [&_li]:list-disc [&_p+p]:mt-4"
                dangerouslySetInnerHTML={{ __html: profile.biography_html }}
              />
            ) : (
              <p className="mt-4 text-sm leading-7 text-muted">
                {profile.summary ?? "No public biography has been added yet."}
              </p>
            )}
          </section>

          <section
            aria-labelledby={`${titleId}-appointment`}
            className="mt-8 border-t border-line pt-7"
          >
            <h3
              className="flex items-center gap-2 text-sm font-extrabold tracking-wide text-[#172f4d] uppercase"
              id={`${titleId}-appointment`}
            >
              <BriefcaseBusiness
                aria-hidden="true"
                className="size-4 text-coral"
              />
              Appointment details
            </h3>
            <dl className="mt-5 grid gap-x-8 gap-y-5 sm:grid-cols-2">
              <div>
                <dt className="text-[.68rem] font-extrabold tracking-wide text-muted uppercase">
                  Academic rank
                </dt>
                <dd className="mt-1 text-sm font-bold text-[#172f4d]">
                  {profile.academic_rank
                    ? formatRankForName(profile.full_name, profile.academic_rank)
                    : "Not provided"}
                </dd>
              </div>
              <div>
                <dt className="text-[.68rem] font-extrabold tracking-wide text-muted uppercase">
                  Term
                </dt>
                <dd className="mt-1 text-sm font-bold text-[#172f4d]">
                  Term {profile.term_number}
                  {profile.is_acting ? " · Acting" : ""}
                </dd>
              </div>
              <div>
                <dt className="text-[.68rem] font-extrabold tracking-wide text-muted uppercase">
                  Appointed
                </dt>
                <dd className="mt-1 flex items-center gap-2 text-sm font-bold text-[#172f4d]">
                  <CalendarDays
                    aria-hidden="true"
                    className="size-4 text-coral"
                  />
                  {formatAppointmentDate(profile.appointed_on)}
                </dd>
              </div>
              <div>
                <dt className="text-[.68rem] font-extrabold tracking-wide text-muted uppercase">
                  Appointment status
                </dt>
                <dd className="mt-1 text-sm font-bold text-[#172f4d]">
                  {profile.is_active ? "Current" : "Past"}
                </dd>
              </div>
            </dl>
          </section>

          {affiliation.length > 0 ? (
            <section
              aria-labelledby={`${titleId}-affiliation`}
              className="mt-8 border-t border-line pt-7"
            >
              <h3
                className="flex items-center gap-2 text-sm font-extrabold tracking-wide text-[#172f4d] uppercase"
                id={`${titleId}-affiliation`}
              >
                <Building2 aria-hidden="true" className="size-4 text-coral" />
                University affiliation
              </h3>
              <p className="mt-4 text-sm leading-7 text-muted">
                {affiliation.join(" · ")}
              </p>
            </section>
          ) : null}

          {socialLinks.length > 0 ? (
            <section
              aria-labelledby={`${titleId}-links`}
              className="mt-8 border-t border-line pt-7"
            >
              <h3
                className="text-sm font-extrabold tracking-wide text-[#172f4d] uppercase"
                id={`${titleId}-links`}
              >
                Professional links
              </h3>
              <div className="mt-4 flex flex-wrap gap-3">
                {socialLinks.map((link) => (
                  <a
                    className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line px-4 text-sm font-bold text-[#172f4d] transition hover:border-[#172f4d]/30 hover:bg-[#f5f8fb]"
                    href={link.url}
                    key={`${link.name}-${link.url}`}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    {link.name}
                    <ExternalLink aria-hidden="true" className="size-4" />
                  </a>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </dialog>
  );
}

export function ExecutiveProfileButton({
  profile,
  className,
}: ExecutiveProfileButtonProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  return (
    <>
      <button
        ref={triggerRef}
        aria-haspopup="dialog"
        className={cn(
          "inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-line px-4 text-sm font-extrabold text-[#172f4d] transition hover:border-[#172f4d]/30 hover:bg-[#f5f8fb]",
          className,
        )}
        onClick={() => setOpen(true)}
        type="button"
      >
        View full profile
        <ArrowUpRight aria-hidden="true" className="size-4" />
      </button>
      {open ? (
        <ExecutiveProfileModal
          onDismiss={() => {
            setOpen(false);
            requestAnimationFrame(() => triggerRef.current?.focus());
          }}
          profile={profile}
        />
      ) : null}
    </>
  );
}
