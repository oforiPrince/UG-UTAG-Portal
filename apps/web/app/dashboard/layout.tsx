import type { Metadata } from "next";
import { Suspense } from "react";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";

export const metadata: Metadata = {
  title: "Dashboard",
  robots: { index: false, follow: false },
};
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardShell>
      <Suspense
        fallback={
          <div
            className="h-[32rem] animate-pulse rounded-2xl bg-ink/5"
            aria-label="Loading dashboard workspace"
          />
        }
      >
        {children}
      </Suspense>
    </DashboardShell>
  );
}
