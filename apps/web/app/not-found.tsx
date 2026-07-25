import Link from "next/link";
import { Button } from "@/components/ui/button";
export default function NotFound() { return <main className="grid min-h-screen place-items-center px-5 text-center"><div><p className="eyebrow text-coral">404 · Not found</p><h1 className="display-type mt-5 text-7xl">This page has moved on.</h1><p className="mt-5 text-sm text-muted">The record may have been archived or the address is incomplete.</p><Button asChild className="mt-8"><Link href="/">Return home</Link></Button></div></main>; }
