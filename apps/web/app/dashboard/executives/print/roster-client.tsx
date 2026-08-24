"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Printer } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { sortLeadership } from "@/lib/leadership";
import { formatPersonName, formatRankForName } from "@/lib/utils";

type Executive = {
  id: string;
  full_name: string;
  title: string;
  academic_rank: string | null;
  position: string;
  portfolio: string | null;
  appointed_on: string | null;
  ended_on: string | null;
  term_number: number;
  is_acting: boolean;
  is_active: boolean;
};

export function ExecutiveRosterClient() {
  const query = useQuery({
    queryKey: ["executives", "print-roster"],
    queryFn: () => api<Executive[]>("/api/v1/executives?include_past=true"),
  });

  const ordered = sortLeadership(query.data ?? []);
  const current = ordered.filter((item) => item.is_active);
  const past = ordered.filter((item) => !item.is_active);

  return (
    <div className="print-roster mx-auto max-w-5xl">
      <div className="print-hidden mb-6 flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="outline">
          <Link href="/dashboard/executives">
            <ArrowLeft className="size-4" /> Back to appointments
          </Link>
        </Button>
        <Button onClick={() => window.print()}>
          <Printer className="size-4" /> Print roster
        </Button>
      </div>

      <header className="border-b-4 border-gold pb-6">
        <p className="text-xs font-black tracking-[.18em] text-coral uppercase">
          University of Ghana branch
        </p>
        <h1 className="display-type mt-3 text-4xl">UTAG executive roster</h1>
        <p className="mt-3 text-sm text-muted">
          Current and past executive appointments
        </p>
      </header>

      {query.isLoading ? (
        <p className="py-16 text-center text-sm text-muted">Loading roster…</p>
      ) : query.error ? (
        <p className="py-16 text-center text-sm text-red-700 dark:text-red-300">
          The executive roster could not be loaded.
        </p>
      ) : (
        <div className="grid gap-10 py-8">
          <RosterSection title="Current executives" items={current} />
          {past.length ? (
            <RosterSection title="Past executives" items={past} />
          ) : null}
        </div>
      )}
    </div>
  );
}

function RosterSection({
  title,
  items,
}: {
  title: string;
  items: Executive[];
}) {
  return (
    <section>
      <div className="mb-4 flex items-end justify-between border-b border-line pb-3">
        <h2 className="text-xl font-black">{title}</h2>
        <span className="text-xs text-muted">
          {items.length} appointment{items.length === 1 ? "" : "s"}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line p-8 text-center text-sm text-muted">
          No appointments recorded.
        </p>
      ) : (
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-line text-[.65rem] tracking-wide text-muted uppercase">
              <th className="py-3 pr-4">Executive</th>
              <th className="px-4 py-3">Position</th>
              <th className="px-4 py-3">Portfolio</th>
              <th className="py-3 pl-4">Term</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {items.map((item) => (
              <tr key={item.id} className="break-inside-avoid">
                <td className="py-4 pr-4">
                  <b>
                    {formatPersonName(
                      [item.title, item.full_name].filter(Boolean).join(" "),
                    )}
                  </b>
                  {item.academic_rank ? (
                    <span className="mt-1 block text-xs text-muted">
                      {formatRankForName(item.full_name, item.academic_rank)}
                    </span>
                  ) : null}
                </td>
                <td className="px-4 py-4">
                  {item.position}
                  {item.is_acting ? " (Acting)" : ""}
                </td>
                <td className="px-4 py-4 text-muted">
                  {item.portfolio || "—"}
                </td>
                <td className="py-4 pl-4">
                  <span>Term {item.term_number}</span>
                  <span className="mt-1 block text-xs text-muted">
                    {item.appointed_on || "Date not recorded"}
                    {item.ended_on ? ` – ${item.ended_on}` : ""}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
