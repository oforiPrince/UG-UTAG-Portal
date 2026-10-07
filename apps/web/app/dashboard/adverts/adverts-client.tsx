"use client";

import { useCallback, useMemo } from "react";
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

  const current =
    ADVERT_TABS.find((tab) => tab.id === activeTab) ?? ADVERT_TABS[0];
  const config = workspaces[current.workspaceKey];

  return (
    <div className="grid gap-4">
      <div
        className="scrollbar-subtle flex gap-2 overflow-x-auto pb-1"
        role="tablist"
      >
        {ADVERT_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => selectTab(tab.id)}
            className={`min-h-10 shrink-0 rounded-full border px-4 text-xs font-bold transition ${
              activeTab === tab.id
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
