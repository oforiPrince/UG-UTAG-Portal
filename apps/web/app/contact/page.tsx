import { Clock3, Mail, MapPin, Phone } from "lucide-react";
import type { Metadata } from "next";

import { PageHero } from "@/components/public/page-hero";
import { PublicShell } from "@/components/public/public-shell";
import { ContactForm } from "./contact-form";

export const metadata: Metadata = { title: "Contact" };

export default function ContactPage() {
  return (
    <PublicShell>
      <PageHero
        eyebrow="Contact"
        title="Contact the UG UTAG Secretariat"
        intro="For association enquiries, media requests and official correspondence, contact the branch secretariat."
      />
      <section className="mx-auto grid max-w-[82rem] gap-10 px-5 py-16 sm:px-6 lg:grid-cols-[.72fr_1.28fr] lg:px-8 lg:py-22">
        <div>
          <p className="text-[.72rem] font-extrabold tracking-[.15em] text-coral uppercase">
            Secretariat
          </p>
          <h2 className="display-type mt-3 text-3xl text-[#172f4d]">
            We are ready to help.
          </h2>
          <p className="mt-4 text-sm leading-7 text-muted">
            Send your enquiry through the secure form or use the official
            contact details below.
          </p>
          <div className="mt-8 grid gap-5">
            <div className="flex gap-4 border-b border-line pb-5">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#edf3f8] text-coral">
                <MapPin className="size-5" />
              </span>
              <div>
                <p className="font-extrabold text-[#172f4d]">Office</p>
                <p className="mt-1 text-sm leading-6 text-muted">
                  University of Ghana
                  <br />
                  Legon, Accra, Ghana
                </p>
              </div>
            </div>
            <div className="flex gap-4 border-b border-line pb-5">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#edf3f8] text-coral">
                <Mail className="size-5" />
              </span>
              <div>
                <p className="font-extrabold text-[#172f4d]">Email</p>
                <a
                  className="mt-1 block text-sm text-muted hover:text-coral"
                  href="mailto:utagoffice@ug.edu.gh"
                >
                  utagoffice@ug.edu.gh
                </a>
              </div>
            </div>
            <div className="flex gap-4 border-b border-line pb-5">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#edf3f8] text-coral">
                <Phone className="size-5" />
              </span>
              <div>
                <p className="font-extrabold text-[#172f4d]">Telephone</p>
                <a
                  className="mt-1 block text-sm text-muted hover:text-coral"
                  href="tel:+233244277275"
                >
                  +233 (0) 24 427 7275
                </a>
              </div>
            </div>
            <div className="flex gap-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#edf3f8] text-coral">
                <Clock3 className="size-5" />
              </span>
              <div>
                <p className="font-extrabold text-[#172f4d]">Opening hours</p>
                <p className="mt-1 text-sm leading-6 text-muted">
                  Monday–Friday
                  <br />
                  9:00 AM–6:00 PM
                </p>
              </div>
            </div>
          </div>
        </div>
        <ContactForm />
      </section>
    </PublicShell>
  );
}
