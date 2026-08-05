import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.PUBLIC_WEB_URL ?? "http://localhost:3000"),
  title: {
    default: "UG UTAG — Scholarship, solidarity, and service",
    template: "%s — UG UTAG",
  },
  description:
    "The official portal of the University of Ghana branch of the University Teachers Association of Ghana.",
  applicationName: "UG UTAG Portal",
  manifest: "/manifest.webmanifest",
  openGraph: {
    type: "website",
    siteName: "UG UTAG",
    title: "UG UTAG",
    description: "The academic voice of the University of Ghana.",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#08111f" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body>
        <a
          href="#main-content"
          className="fixed top-3 left-3 z-[100] -translate-y-24 rounded-full bg-ink px-4 py-2 text-sm font-bold text-paper transition-transform focus:translate-y-0"
        >
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
