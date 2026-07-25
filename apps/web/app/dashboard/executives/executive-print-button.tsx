"use client";

import { Printer } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function ExecutivePrintButton() {
  return (
    <Button asChild variant="outline">
      <Link href="/dashboard/executives/print">
        <Printer className="size-4" /> Print roster
      </Link>
    </Button>
  );
}
