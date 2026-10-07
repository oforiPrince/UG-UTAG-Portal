import { notFound } from "next/navigation";
import { Suspense } from "react";

import { WorkspaceRecordPage } from "@/components/dashboard/workspace-record-page";
import { routedWorkspace } from "@/lib/workspace-presentation";

export default async function NewWorkspaceRecordPage({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  const routed = routedWorkspace(section);
  if (!routed) notFound();
  return (
    <Suspense
      fallback={
        <div className="h-[42rem] animate-pulse rounded-3xl bg-ink/5" />
      }
    >
      <WorkspaceRecordPage configKey={routed.configKey} mode="create" />
    </Suspense>
  );
}
