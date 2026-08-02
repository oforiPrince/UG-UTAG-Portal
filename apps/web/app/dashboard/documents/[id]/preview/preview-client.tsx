"use client";

import { useQuery } from "@tanstack/react-query";
import { FileWarning, LoaderCircle } from "lucide-react";
import Link from "next/link";

import { DocumentPreview } from "@/components/documents/document-preview";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { type MemberDocument, memberDocumentPreview } from "@/lib/documents";

export function MemberDocumentPreviewClient({ id }: { id: string }) {
  const document = useQuery({
    queryKey: ["documents", "preview", id],
    queryFn: () =>
      api<MemberDocument>(`/api/v1/documents/${encodeURIComponent(id)}`),
    retry: false,
  });

  if (document.isLoading) {
    return (
      <div className="grid min-h-96 place-items-center">
        <LoaderCircle
          className="size-8 animate-spin text-coral"
          aria-label="Loading document preview"
        />
      </div>
    );
  }

  if (!document.data || document.error) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <FileWarning className="mx-auto size-9 text-coral" />
          <h1 className="mt-4 text-xl font-black">
            This document preview could not be loaded.
          </h1>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">
            The document may no longer be available to your account, or its
            files may still be completing security checks.
          </p>
          <Button asChild className="mt-6" variant="outline">
            <Link href="/dashboard/documents">Back to documents</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <DocumentPreview
      document={memberDocumentPreview(document.data)}
      backHref="/dashboard/documents"
      backLabel="Documents"
      privateView
    />
  );
}
