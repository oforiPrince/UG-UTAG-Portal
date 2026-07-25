"use client";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <main className="grid min-h-screen place-items-center px-5 text-center"><div><AlertTriangle className="mx-auto size-8 text-coral" /><h1 className="display-type mt-6 text-6xl">Something interrupted the page.</h1><p className="mt-4 text-sm text-muted">No changes were lost. Try loading this view again.</p><Button className="mt-7" onClick={reset}>Try again</Button></div></main>; }
