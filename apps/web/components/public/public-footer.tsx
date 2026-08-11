import { Clock3, Mail, MapPin, Phone } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/logo";
import type {
  PublicContact,
  PublicFeatures,
  PublicFooterSettings,
} from "@/lib/public-site";
import { phoneHref } from "@/lib/public-site";

export function PublicFooter({
  contact,
  features,
  settings,
}: {
  contact: PublicContact;
  features: PublicFeatures;
  settings: PublicFooterSettings;
}) {
  const telephoneHref = phoneHref(contact.phone);
  return (
    <footer className="mt-20 bg-[#102742] text-white">
      <div className="border-b border-white/10 bg-[#c79a2b] text-[#142a45]">
        <div className="mx-auto grid w-full min-w-0 max-w-[82rem] gap-4 px-4 py-5 text-sm font-bold sm:grid-cols-3 sm:px-6 lg:px-8">
          <span className="flex min-w-0 items-start gap-3 break-words">
            <MapPin className="mt-0.5 size-5 shrink-0" /> {contact.address}
          </span>
          {contact.email ? (
            <a
              className="flex min-w-0 items-start gap-3 break-all hover:underline"
              href={`mailto:${contact.email}`}
            >
              <Mail className="mt-0.5 size-5 shrink-0" /> {contact.email}
            </a>
          ) : (
            <span />
          )}
          {contact.phone ? (
            <a
              className="flex min-w-0 items-start gap-3 break-words hover:underline"
              href={`tel:${telephoneHref}`}
            >
              <Phone className="mt-0.5 size-5 shrink-0" /> {contact.phone}
            </a>
          ) : (
            <span />
          )}
        </div>
      </div>

      <div className="mx-auto grid w-full min-w-0 max-w-[82rem] gap-10 px-4 py-14 sm:px-6 md:grid-cols-2 lg:grid-cols-[1.35fr_.65fr_.65fr_.85fr] lg:px-8">
        <div>
          <Logo inverse />
          <p className="mt-6 max-w-md text-sm leading-7 text-white/66">
            {settings.membership_note}
          </p>
        </div>
        <div>
          <h2 className="text-sm font-extrabold text-gold">About UG UTAG</h2>
          <div className="mt-5 grid gap-3 text-sm text-white/68">
            <Link href="/about" className="hover:text-white">
              About us
            </Link>
            <Link href="/leadership" className="hover:text-white">
              Leadership
            </Link>
            <Link href="/news" className="hover:text-white">
              News
            </Link>
            <Link href="/events" className="hover:text-white">
              Events
            </Link>
          </div>
        </div>
        <div>
          <h2 className="text-sm font-extrabold text-gold">Quick links</h2>
          <div className="mt-5 grid gap-3 text-sm text-white/68">
            {features["public-resources"] ? (
              <Link href="/resources" className="hover:text-white">
                Resources
              </Link>
            ) : null}
            {features["public-gallery"] ? (
              <Link href="/gallery" className="hover:text-white">
                Gallery
              </Link>
            ) : null}
            <a
              href="https://ugresearch.ug.edu.gh/"
              className="hover:text-white"
            >
              UG Research
            </a>
            <Link href="/contact" className="hover:text-white">
              Contact us
            </Link>
            <Link href="/login" className="hover:text-white">
              Member portal
            </Link>
          </div>
        </div>
        <div>
          <h2 className="text-sm font-extrabold text-gold">
            Secretariat hours
          </h2>
          <p className="mt-5 flex gap-3 text-sm leading-7 text-white/68">
            <Clock3 className="mt-1 size-4 shrink-0 text-gold" />
            {contact.office_hours}
          </p>
        </div>
      </div>

      <div className="border-t border-white/10">
        <div className="mx-auto flex w-full min-w-0 max-w-[82rem] flex-col gap-2 px-4 py-5 text-[.7rem] text-white/45 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span className="break-words">
            © {new Date().getFullYear()} {settings.copyright_name}. All rights
            reserved.
          </span>
          <span>Scholarship · Welfare · Academic freedom</span>
        </div>
      </div>
    </footer>
  );
}
