import {
  CheckCircle2,
  FlaskConical,
  GraduationCap,
  HeartHandshake,
  Megaphone,
} from "lucide-react";
import type { Metadata } from "next";

import { PageHero } from "@/components/public/page-hero";
import { PublicShell } from "@/components/public/public-shell";

export const metadata: Metadata = { title: "About us" };

const commitments = [
  [
    GraduationCap,
    "Quality Education",
    "Defend academic freedom and support the conditions required for excellent teaching.",
  ],
  [
    FlaskConical,
    "Teaching & Research",
    "Advance research, scholarship, mentorship, and community service across the University.",
  ],
  [
    Megaphone,
    "Member Advocacy",
    "Represent members with clarity before University Management, National Leadership of UTAG, and government.",
  ],
  [
    HeartHandshake,
    "Member Welfare",
    "Promote fair conditions, professional wellbeing, and mutual support for University teachers.",
  ],
] as const;

export default function AboutPage() {
  return (
    <PublicShell>
      <PageHero
        eyebrow="About us"
        title="University of Ghana Branch of UTAG"
        intro="A united association representing teaching and research staff and advancing their academic, professional, and economic welfare."
      />

      <section className="mx-auto grid max-w-[82rem] gap-6 px-5 py-14 sm:grid-cols-2 sm:px-6 lg:grid-cols-4 lg:px-8 lg:py-18">
        {commitments.map(([Icon, title, description]) => (
          <article key={title} className="border-t-4 border-gold bg-panel p-6">
            <Icon className="size-7 text-coral" />
            <h2 className="mt-5 text-lg font-extrabold text-[#172f4d]">
              {title}
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted">{description}</p>
          </article>
        ))}
      </section>

      <section className="bg-[#f5f8fb] px-5 py-16 sm:px-6 lg:px-8 lg:py-22">
        <div className="mx-auto grid max-w-[82rem] gap-12 lg:grid-cols-[1.05fr_.95fr] lg:items-center">
          <div>
            <p className="text-[.72rem] font-extrabold tracking-[.15em] text-coral uppercase">
              Who we are
            </p>
            <h2 className="display-type mt-4 text-3xl leading-tight text-[#172f4d] sm:text-4xl">
              Welcome to UG UTAG
            </h2>
            <div className="mt-5 h-1 w-16 bg-gold" />
            <p className="mt-6 text-sm leading-7 text-muted sm:text-base">
              The University of Ghana Branch of the University Teachers
              Association of Ghana represents the teaching and research staff of
              the University. We promote the academic, professional and economic
              welfare of members and the wider academic community.
            </p>
            <p className="mt-4 text-sm leading-7 text-muted sm:text-base">
              The association engages University Management, National leadership of UTAG,
              and institutions of state on matters affecting members, academic
              life, and the quality of higher education. Our work is guided by
              the the National constitution of UTAG and Branch By-laws.
            </p>
            <ul className="mt-6 grid gap-3 text-sm font-semibold text-[#2d4056] sm:grid-cols-2">
              {[
                "Defend Academic Freedom",
                "Advance Teaching and Research",
                "Advocate for Member Needs",
                "Foster Healthy University Relations",
              ].map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-gold" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="overflow-hidden rounded-md border border-line bg-white p-2 shadow-[0_18px_45px_rgb(23_43_69_/_12%)]">
            <div
              className="aspect-[16/10] bg-cover bg-center"
              style={{ backgroundImage: "url('/brand/campus-gate.png')" }}
              role="img"
              aria-label="University of Ghana campus entrance"
            />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[82rem] px-5 py-16 sm:px-6 lg:px-8 lg:py-22">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-[.72rem] font-extrabold tracking-[.15em] text-coral uppercase">
            Our purpose
          </p>
          {/* <h2 className="display-type mt-3 text-3xl text-[#172f4d] sm:text-4xl">
            Principled representation. Practical service.
          </h2> */}
          <p className="mt-4 text-sm leading-7 text-muted sm:text-base">
            We bring academics together to protect shared interests,
            strengthen the University of Ghana, and serve society through knowledge.
          </p>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {[
            "Academic Freedom and Responsibility",
            "Transparent and Inclusive Governance",
            "Solidarity across Rank and Discipline",
          ].map((value, index) => (
            <article
              key={value}
              className="rounded-md border border-line bg-white p-7 shadow-sm"
            >
              <span className="text-xs font-black text-gold">0{index + 1}</span>
              <h3 className="mt-8 text-xl font-extrabold leading-snug text-[#172f4d]">
                {value}
              </h3>
            </article>
          ))}
        </div>
      </section>
    </PublicShell>
  );
}
