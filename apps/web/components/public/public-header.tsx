"use client";

import {
  ChevronDown,
  Clock3,
  Mail,
  Menu,
  Search,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/logo";
import type { PublicContact, PublicFeatures } from "@/lib/public-site";
import { cn } from "@/lib/utils";

const links = [
  ["Home", "/"],
  ["About us", "/about"],
  ["News", "/news"],
  ["Events", "/events"],
  ["Gallery", "/gallery"],
  ["Contact", "/contact"],
] as const;

const leadershipLinks = [
  ["Executive Officers", "/leadership#executive-officers"],
  [
    "Local Executive Council Members",
    "/leadership#local-executive-council-members",
  ],
] as const;

export function PublicHeader({
  contact,
  features,
}: {
  contact: PublicContact;
  features: PublicFeatures;
}) {
  const [open, setOpen] = useState(false);
  const [leadershipOpen, setLeadershipOpen] = useState(false);
  const pathname = usePathname();
  const leadershipActive = pathname.startsWith("/leadership");
  const visibleLinks = links.filter(
    ([, href]) => href !== "/gallery" || features["public-gallery"],
  );

  function closeMobileNavigation() {
    setOpen(false);
    setLeadershipOpen(false);
  }

  return (
    <header className="sticky top-0 z-50 bg-white shadow-[0_2px_14px_rgb(23_43_69_/_8%)]">
      <div className="hidden bg-[#172f4d] text-white sm:block">
        <div className="mx-auto flex min-h-9 max-w-[82rem] items-center justify-between px-6 text-[.69rem] lg:px-8">
          <div className="flex items-center gap-5 text-white/78">
            <span className="inline-flex items-center gap-2">
              <Clock3 className="size-3.5 text-gold" /> {contact.office_hours}
            </span>
            {contact.email ? (
              <a
                className="hidden items-center gap-2 hover:text-white md:inline-flex"
                href={`mailto:${contact.email}`}
              >
                <Mail className="size-3.5 text-gold" /> {contact.email}
              </a>
            ) : null}
          </div>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 font-bold hover:text-gold"
          >
            <UserRound className="size-3.5" /> Member login
          </Link>
        </div>
      </div>

      <div className="mx-auto flex h-[4.75rem] w-full min-w-0 max-w-[82rem] items-center justify-between gap-3 px-4 sm:h-[5.25rem] sm:px-6 lg:px-8">
        <Logo />
        <nav
          className="hidden items-center gap-0.5 xl:flex"
          aria-label="Main navigation"
        >
          {visibleLinks.slice(0, 2).map(([label, href]) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "relative px-3 py-8 text-[.78rem] font-bold text-[#2d3d51] transition-colors hover:text-coral",
                  active &&
                    "text-coral after:absolute after:right-3 after:bottom-0 after:left-3 after:h-0.5 after:bg-gold",
                )}
              >
                {label}
              </Link>
            );
          })}
          <div className="group relative self-stretch">
            <Link
              href="/leadership"
              aria-haspopup="true"
              className={cn(
                "relative inline-flex h-full items-center gap-1 px-3 text-[.78rem] font-bold text-[#2d3d51] transition-colors hover:text-coral",
                leadershipActive &&
                  "text-coral after:absolute after:right-3 after:bottom-0 after:left-3 after:h-0.5 after:bg-gold",
              )}
            >
              Leadership
              <ChevronDown className="size-3.5 transition-transform group-hover:rotate-180 group-focus-within:rotate-180" />
            </Link>
            <nav
              aria-label="Leadership sections"
              className="invisible absolute top-full left-0 z-50 w-72 translate-y-2 border-t-2 border-gold bg-white p-2 opacity-0 shadow-[0_16px_38px_rgb(23_43_69_/_18%)] transition duration-150 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100"
            >
              {leadershipLinks.map(([label, href]) => (
                <Link
                  key={href}
                  href={href}
                  className="flex min-h-11 items-center border-b border-line/70 px-4 py-3 text-sm font-bold text-[#2d3d51] transition last:border-b-0 hover:bg-panel hover:text-coral focus-visible:bg-panel"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
          {visibleLinks.slice(2).map(([label, href]) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "relative px-3 py-8 text-[.78rem] font-bold text-[#2d3d51] transition-colors hover:text-coral",
                  active &&
                    "text-coral after:absolute after:right-3 after:bottom-0 after:left-3 after:h-0.5 after:bg-gold",
                )}
              >
                {label}
              </Link>
            );
          })}
          <Link
            href="/search"
            aria-label="Search"
            className="ml-2 grid size-10 place-items-center rounded-full border border-line text-ink transition hover:border-coral hover:text-coral"
          >
            <Search className="size-4" />
          </Link>
        </nav>

        <button
          className="grid size-11 place-items-center rounded-md border border-line bg-panel text-ink xl:hidden"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls="public-mobile-navigation"
          aria-label={open ? "Close navigation" : "Open navigation"}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      {open && (
        <nav
          id="public-mobile-navigation"
          className="border-t border-line bg-white px-4 py-4 shadow-lg xl:hidden"
          aria-label="Mobile navigation"
        >
          <div className="mx-auto grid max-w-2xl sm:grid-cols-2">
            {visibleLinks.slice(0, 2).map(([label, href]) => (
              <Link
                key={href}
                href={href}
                onClick={closeMobileNavigation}
                className="border-b border-line/70 px-3 py-3.5 text-sm font-bold text-ink hover:bg-panel hover:text-coral sm:mx-1"
              >
                {label}
              </Link>
            ))}
            <div className="border-b border-line/70 sm:mx-1">
              <button
                type="button"
                className="flex min-h-12 w-full items-center justify-between px-3 py-3 text-left text-sm font-bold text-ink hover:bg-panel hover:text-coral"
                onClick={() => setLeadershipOpen((value) => !value)}
                aria-expanded={leadershipOpen}
                aria-controls="mobile-leadership-submenu"
              >
                Leadership
                <ChevronDown
                  className={cn(
                    "size-4 transition-transform",
                    leadershipOpen && "rotate-180",
                  )}
                />
              </button>
              {leadershipOpen && (
                <div
                  id="mobile-leadership-submenu"
                  className="border-t border-line bg-panel px-2 py-2"
                >
                  {leadershipLinks.map(([label, href]) => (
                    <Link
                      key={href}
                      href={href}
                      onClick={closeMobileNavigation}
                      className="flex min-h-11 items-center border-b border-line/70 px-4 py-2.5 text-sm font-semibold text-[#40546a] last:border-b-0 hover:bg-white hover:text-coral"
                    >
                      {label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
            {visibleLinks.slice(2).map(([label, href]) => (
              <Link
                key={href}
                href={href}
                onClick={closeMobileNavigation}
                className="border-b border-line/70 px-3 py-3.5 text-sm font-bold text-ink hover:bg-panel hover:text-coral sm:mx-1"
              >
                {label}
              </Link>
            ))}
            <Link
              href="/search"
              onClick={closeMobileNavigation}
              className="mt-3 inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-line text-sm font-bold sm:mx-1"
            >
              <Search className="size-4" /> Search
            </Link>
            <Link
              href="/login"
              onClick={closeMobileNavigation}
              className="mt-3 inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-[#172f4d] text-sm font-bold text-white sm:mx-1"
            >
              <UserRound className="size-4" /> Member portal
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
