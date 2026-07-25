"use client";

import { WorkspaceClient } from "@/components/dashboard/workspace-client";
import { workspaces } from "@/lib/workspaces";

import { MemberImportButton } from "./member-import-button";

export default function MembersPage() {
  return <WorkspaceClient config={workspaces.members} headerAction={<MemberImportButton />} />;
}
