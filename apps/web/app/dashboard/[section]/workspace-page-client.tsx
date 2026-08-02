"use client";

import { notFound } from "next/navigation";

import { WorkspaceClient } from "@/components/dashboard/workspace-client";
import { workspaces } from "@/lib/workspaces";

import { MemberImportButton } from "../members/member-import-button";
import { ExecutivePrintButton } from "../executives/executive-print-button";

export function WorkspacePageClient({ section }: { section: string }) {
  const config = workspaces[section];
  if (!config) notFound();
  return (
    <WorkspaceClient
      config={config}
      headerAction={
        section === "members" ? (
          <MemberImportButton />
        ) : section === "executives" ? (
          <ExecutivePrintButton />
        ) : undefined
      }
    />
  );
}
