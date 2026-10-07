import { Suspense } from "react";

import { WorkspaceRecordPage } from "@/components/dashboard/workspace-record-page";

export default function NewGalleryPage() {
  return (
    <Suspense
      fallback={
        <div className="h-[42rem] animate-pulse rounded-3xl bg-ink/5" />
      }
    >
      <WorkspaceRecordPage configKey="galleries" mode="create" />
    </Suspense>
  );
}
