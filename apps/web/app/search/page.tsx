import type { Metadata } from "next";

import { PageHero } from "@/components/public/page-hero";
import { PublicShell } from "@/components/public/public-shell";
import { SearchClient } from "./search-client";

export const metadata: Metadata = { title: "Search" };

export default function SearchPage() {
  return (
    <PublicShell>
      <PageHero
        eyebrow="Search"
        title="Search the UG UTAG website"
        intro="Find news, events, public resources and leadership information."
      />
      <section className="mx-auto max-w-4xl px-5 py-14 sm:px-6 lg:py-18">
        <SearchClient />
      </section>
    </PublicShell>
  );
}
