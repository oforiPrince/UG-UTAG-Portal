"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import { humanize } from "@/lib/utils";

type Result = {
  id: string;
  kind: string;
  title: string;
  excerpt: string;
  url: string;
};

export function SearchClient() {
  const [query, setQuery] = useState("");
  const results = useQuery({
    queryKey: ["search", query],
    queryFn: () =>
      api<Result[]>(`/api/v1/public/search?q=${encodeURIComponent(query)}`),
    enabled: query.trim().length >= 2,
  });
  return (
    <div>
      <label className="flex min-h-16 items-center gap-4 rounded-md border border-line bg-panel px-5 shadow-sm focus-within:border-coral focus-within:ring-2 focus-within:ring-sky/15">
        <Search className="size-5 text-coral" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoFocus
          placeholder="Search news, events and resources"
          className="w-full bg-transparent text-base outline-none sm:text-lg"
        />
      </label>
      <div className="mt-8 divide-y divide-line">
        {results.data?.map((result) => (
          <Link
            key={`${result.kind}-${result.id}`}
            href={result.url}
            className="group grid grid-cols-[1fr_auto] gap-6 py-6"
          >
            <div>
              <p className="eyebrow text-coral">{humanize(result.kind)}</p>
              <h2 className="mt-2 text-xl font-black text-[#172f4d] group-hover:text-coral">
                {result.title}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                {result.excerpt}
              </p>
            </div>
            <ArrowUpRight className="mt-1 size-5 text-muted" />
          </Link>
        ))}
      </div>
      {query.length >= 2 &&
        !results.isLoading &&
        results.data?.length === 0 && (
          <p className="py-16 text-center text-sm text-muted">
            No results found. Try a broader search.
          </p>
        )}
    </div>
  );
}
