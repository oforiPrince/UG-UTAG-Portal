import { redirect } from "next/navigation";

import { WorkspacePageClient } from "./workspace-page-client";

export default async function WorkspacePage({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (section === "administrators") redirect("/dashboard/members");
  return <WorkspacePageClient section={section} />;
}
