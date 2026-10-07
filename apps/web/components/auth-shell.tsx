import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/logo";

export function AuthShell({ title, intro, children }: { title: string; intro: string; children: React.ReactNode }) {
  return <main id="main-content" className="grid min-h-screen bg-paper lg:grid-cols-[.92fr_1.08fr]"><section className="relative hidden overflow-hidden bg-[#0a172b] p-12 text-white lg:flex lg:flex-col lg:justify-between"><div className="absolute inset-0 hairline-grid opacity-10" /><div className="relative"><Logo inverse /></div><div className="relative max-w-xl"><p className="eyebrow text-gold">Secure member workspace</p><blockquote className="display-type mt-6 text-5xl leading-[1.02]">“An association is strongest when its knowledge, people, and purpose stay connected.”</blockquote></div><p className="relative text-xs text-white/40">Private by design · Live by default · Built for UG UTAG</p></section><section className="flex min-h-screen items-center justify-center px-5 py-12 sm:px-8"><div className="w-full max-w-md"><div className="mb-10 flex items-center justify-between lg:hidden"><Logo /><Link href="/" aria-label="Back home"><ArrowLeft className="size-5" /></Link></div><p className="eyebrow text-coral">Member access</p><h1 className="display-type mt-4 text-5xl">{title}</h1><p className="mt-4 text-sm leading-7 text-muted">{intro}</p><div className="mt-9">{children}</div></div></section></main>;
}
