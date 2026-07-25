import { Clock3, Mail, MapPin, Phone } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/logo";

export function PublicFooter() {
  return (
    <footer className="mt-20 bg-[#102742] text-white">
      <div className="border-b border-white/10 bg-[#c79a2b] text-[#142a45]">
        <div className="mx-auto grid max-w-[82rem] gap-4 px-5 py-5 text-sm font-bold sm:grid-cols-3 sm:px-6 lg:px-8">
          <span className="inline-flex items-center gap-3">
            <MapPin className="size-5" /> University of Ghana, Legon
          </span>
          <a
            className="inline-flex items-center gap-3 hover:underline"
            href="mailto:utagoffice@ug.edu.gh"
          >
            <Mail className="size-5" /> utagoffice@ug.edu.gh
          </a>
          <a
            className="inline-flex items-center gap-3 hover:underline"
            href="tel:+233244277275"
          >
            <Phone className="size-5" /> +233 (0) 24 427 7275
          </a>
        </div>
      </div>

      <div className="mx-auto grid max-w-[82rem] gap-10 px-5 py-14 sm:px-6 md:grid-cols-2 lg:grid-cols-[1.35fr_.65fr_.65fr_.85fr] lg:px-8">
        <div>
          <Logo inverse />
          <p className="mt-6 max-w-md text-sm leading-7 text-white/66">
            Representing teaching and research staff while advancing academic
            excellence, professional welfare and service to the University
            community.
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
            <Link href="/resources" className="hover:text-white">
              Resources
            </Link>
            <Link href="/gallery" className="hover:text-white">
              Gallery
            </Link>
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
            <Clock3 className="mt-1 size-4 shrink-0 text-gold" /> Monday to
            Friday
            <br />
            9:00 AM–6:00 PM
          </p>
        </div>
      </div>

      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-[82rem] flex-col gap-2 px-5 py-5 text-[.7rem] text-white/45 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span>
            © {new Date().getFullYear()} University of Ghana Branch of UTAG. All
            rights reserved.
          </span>
          <span>Scholarship · Welfare · Academic freedom</span>
        </div>
      </div>
    </footer>
  );
}
