import { WifiOff } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

export default function OfflinePage() {
  return <main className="grid min-h-screen place-items-center px-5"><div className="max-w-md text-center"><div className="flex justify-center"><Logo /></div><span className="mx-auto mt-14 grid size-16 place-items-center rounded-2xl bg-ink/5"><WifiOff className="size-7 text-coral" /></span><h1 className="display-type mt-7 text-5xl">You are offline.</h1><p className="mt-4 text-sm leading-7 text-muted">Previously visited public pages remain available. Secure dashboard data will resync when your connection returns.</p><Button asChild className="mt-7"><Link href="/">Return home</Link></Button></div></main>;
}
