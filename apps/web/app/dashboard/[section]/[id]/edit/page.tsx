import { notFound } from "next/navigation";
import { Suspense } from "react";

import { WorkspaceRecordPage } from "@/components/dashboard/workspace-record-page";
import { routedWorkspace } from "@/lib/workspace-presentation";

export default async function WorkspaceRecordEditPage({
  params,
}: {
  params: Promise<{ section: string; id: string }>;
}) {
  const { section, id } = await params;
  const routed = routedWorkspace(section);
  if (!routed) notFound();
  return (
    <Suspense
      fallback={
        <div className="h-[42rem] animate-pulse rounded-3xl bg-ink/5" />
      }
    >
      <WorkspaceRecordPage
        configKey={routed.configKey}
        mode="edit"
        recordId={id}
      />
    </Suspense>
  );
}
