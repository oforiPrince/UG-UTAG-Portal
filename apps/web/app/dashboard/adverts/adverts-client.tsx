"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { WorkspaceClient } from "@/components/dashboard/workspace-client";
import { workspaces } from "@/lib/workspaces";

const ADVERT_TABS = [
  {
    id: "campaigns",
    label: "Campaigns",
    workspaceKey: "adverts",
  },
  {
    id: "clients",
    label: "Clients",
    workspaceKey: "advert-advertisers",
  },
  {
    id: "placements",
    label: "Placements",
    workspaceKey: "advert-slots",
  },
  {
    id: "plans",
    label: "Plans",
    workspaceKey: "advert-plans",
  },
  {
    id: "orders",
    label: "Orders",
    workspaceKey: "advert-orders",
  },
] as const;

type AdvertTabId = (typeof ADVERT_TABS)[number]["id"];

const TAB_IDS = new Set<string>(ADVERT_TABS.map((tab) => tab.id));

function resolveTab(value: string | null): AdvertTabId {
  if (value && TAB_IDS.has(value)) return value as AdvertTabId;
  return "campaigns";
}

export function AdvertsClient() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeTab = useMemo(
    () => resolveTab(searchParams.get("tab")),
    [searchParams],
  );

  const [mountedTab, setMountedTab] = useState<AdvertTabId>(activeTab);

  useEffect(() => {
    setMountedTab(activeTab);
  }, [activeTab]);

  const selectTab = useCallback(
    (tab: AdvertTabId) => {
      const params = new URLSearchParams(searchParams.toString());
      if (tab === "campaigns") params.delete("tab");
      else params.set("tab", tab);
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );

  const current = ADVERT_TABS.find((tab) => tab.id === mountedTab) ?? ADVERT_TABS[0];
  const config = workspaces[current.workspaceKey];

  return (
    <div className="grid gap-5">
      <header>
        <p className="eyebrow text-coral">Commercial inventory</p>
        <h2 className="display-type mt-3 text-4xl sm:text-5xl">Advertising</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
          Sell placements to external companies and clients, manage rate-card
          plans, live campaigns and orders from one workspace. Advertisers do
          not need to be portal members.
        </p>
      </header>

      <div className="scrollbar-subtle flex gap-2 overflow-x-auto pb-1" role="tablist">
        {ADVERT_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={mountedTab === tab.id}
            onClick={() => selectTab(tab.id)}
            className={`min-h-10 shrink-0 rounded-full border px-4 text-xs font-bold transition ${
              mountedTab === tab.id
                ? "border-ink bg-ink text-paper"
                : "border-line bg-panel text-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {config ? (
        <WorkspaceClient key={current.workspaceKey} config={config} embedded />
      ) : null}
    </div>
  );
}
