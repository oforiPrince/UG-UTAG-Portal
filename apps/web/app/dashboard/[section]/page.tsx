import { redirect } from "next/navigation";

import { WorkspacePageClient } from "./workspace-page-client";

const ADVERT_SECTION_TABS: Record<string, string> = {
  "advert-advertisers": "/dashboard/adverts?tab=clients",
  "advert-slots": "/dashboard/adverts?tab=placements",
  "advert-plans": "/dashboard/adverts?tab=plans",
  "advert-orders": "/dashboard/adverts?tab=orders",
};

export default async function WorkspacePage({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (section === "administrators") redirect("/dashboard/members");
  const advertRedirect = ADVERT_SECTION_TABS[section];
  if (advertRedirect) redirect(advertRedirect);
  return <WorkspacePageClient section={section} />;
}
