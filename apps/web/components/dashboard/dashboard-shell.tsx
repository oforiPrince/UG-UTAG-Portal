"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  Command,
  LogOut,
  Menu,
  Moon,
  Search,
  Sun,
  X,
} from "lucide-react";
import { useTheme } from "next-themes";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Logo } from "@/components/logo";
import { NotificationBell } from "@/components/dashboard/notification-bell";
import { useRealtime } from "@/components/realtime-provider";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { navigation } from "@/lib/navigation";
import { cn, initials } from "@/lib/utils";

type User = {
  id: string;
  full_name: string;
  email: string;
  profile_media_id: string | null;
  must_change_password: boolean;
  roles: string[];
  permissions: string[];
};

function LiveState() {
  const { state } = useRealtime();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[.65rem] font-bold",
        state === "live"
          ? "border-emerald-500/20 bg-emerald-500/8 text-emerald-700 dark:text-emerald-300"
          : state === "connecting"
            ? "border-gold/25 bg-gold/8 text-ink"
            : "border-line bg-panel text-muted",
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          state === "live"
            ? "animate-pulse bg-emerald-500"
            : state === "connecting"
              ? "animate-pulse bg-gold"
              : "bg-muted",
        )}
      />
      {state === "live"
        ? "Live"
        : state === "connecting"
          ? "Connecting"
          : "Offline"}
    </span>
  );
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const user = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api<User>("/api/v1/auth/me"),
    retry: false,
  });
  useEffect(() => {
    if (user.error)
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [user.error, router, pathname]);
  useEffect(() => {
    if (user.data?.must_change_password && pathname !== "/dashboard/profile") {
      router.replace("/dashboard/profile?password=required");
    }
  }, [pathname, router, user.data?.must_change_password]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const items = useMemo(
    () =>
      navigation.filter(
        (item) => !user.data || user.data.permissions.includes(item.permission),
      ),
    [user.data],
  );
  const groups = [...new Set(items.map((item) => item.group))];
  const current =
    items.find((item) => item.href === pathname) ??
    items.find((item) => pathname.startsWith(`${item.href}/`));
  const commandItems = items.filter((item) =>
    item.label.toLowerCase().includes(commandQuery.toLowerCase()),
  );
  async function logout() {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
      router.replace("/login");
      router.refresh();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not sign out",
      );
    }
  }

  const sidebar = (
    <>
      <div className="flex h-[4.75rem] items-center justify-between px-5">
        <Logo inverse />
        <button
          className="text-white/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        >
          <X className="size-5" />
        </button>
      </div>
      <nav className="scrollbar-subtle flex-1 overflow-y-auto px-3 py-4">
        {groups.map((group) => (
          <div key={group} className="mb-5">
            <p className="px-3 pb-2 text-[.58rem] font-black tracking-[.16em] text-white/30 uppercase">
              {group}
            </p>
            <div className="grid gap-1">
              {items
                .filter((item) => item.group === group)
                .map((item) => {
                  const Icon = item.icon;
                  const active = item.href === pathname;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "flex min-h-10 items-center gap-3 rounded-xl px-3 text-[.78rem] font-bold text-white/55 transition hover:bg-white/7 hover:text-white",
                        active && "bg-white/10 text-white shadow-inner",
                      )}
                    >
                      <Icon
                        className={cn("size-[1.05rem]", active && "text-gold")}
                      />
                      {item.label}
                    </Link>
                  );
                })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-white/10 p-3">
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-xs font-bold text-white/50 hover:bg-white/7 hover:text-white"
        >
          <LogOut className="size-4" /> Sign out
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-paper">
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-[17rem] flex-col bg-[#091529] lg:flex">
        {sidebar}
      </aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            className="absolute inset-0 bg-black/45 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation backdrop"
          />
          <aside className="relative flex h-full w-[min(19rem,88vw)] flex-col bg-[#091529] shadow-2xl">
            {sidebar}
          </aside>
        </div>
      )}
      <div className="lg:pl-[17rem]">
        <header className="sticky top-0 z-40 flex h-[4.75rem] items-center justify-between border-b border-line bg-paper/88 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <button
              className="grid size-10 place-items-center rounded-xl border border-line bg-panel lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="size-5" />
            </button>
            <div>
              <p className="text-[.62rem] font-bold tracking-[.12em] text-muted uppercase">
                Member workspace
              </p>
              <h1 className="mt-0.5 text-base font-black">
                {current?.label ?? "Dashboard"}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-2">
            <span className="hidden sm:inline-flex">
              <LiveState />
            </span>
            <button
              onClick={() => setCommandOpen(true)}
              className="hidden min-h-10 items-center gap-3 rounded-xl border border-line bg-panel px-3 text-xs text-muted xl:flex"
            >
              <Search className="size-4" /> Search{" "}
              <kbd className="rounded border border-line bg-paper px-1.5 py-0.5 text-[.58rem]">
                ⌘K
              </kbd>
            </button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() =>
                setTheme(resolvedTheme === "dark" ? "light" : "dark")
              }
              aria-label="Toggle theme"
            >
              {resolvedTheme === "dark" ? (
                <Sun className="size-4" />
              ) : (
                <Moon className="size-4" />
              )}
            </Button>
            <NotificationBell enabled={Boolean(user.data)} />
            <Link
              href="/dashboard/profile"
              className="ml-1 flex items-center gap-2 rounded-full border border-line bg-panel p-1 pr-2"
            >
              <span className="relative grid size-8 place-items-center overflow-hidden rounded-full bg-ink text-[.65rem] font-black text-paper">
                {user.data?.profile_media_id ? (
                  <Image
                    fill
                    unoptimized
                    alt=""
                    className="object-cover"
                    sizes="32px"
                    src={`/api/v1/media/${user.data.profile_media_id}/content`}
                  />
                ) : (
                  initials(user.data?.full_name ?? "UG")
                )}
              </span>
              <ChevronDown className="hidden size-3 text-muted sm:block" />
            </Link>
          </div>
        </header>
        <main
          id="main-content"
          className="mx-auto max-w-[105rem] px-4 py-5 pb-24 sm:px-6 sm:py-7 lg:px-8 lg:pb-8"
        >
          {children}
        </main>
      </div>
      <nav className="fixed right-3 bottom-3 left-3 z-40 grid grid-cols-5 rounded-[1.25rem] border border-white/10 bg-[#091529]/95 p-1.5 shadow-2xl backdrop-blur-xl lg:hidden">
        {items.slice(0, 4).map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex min-h-12 flex-col items-center justify-center gap-1 rounded-xl text-[.54rem] font-bold text-white/45",
                active && "bg-white/10 text-white",
              )}
            >
              <Icon className={cn("size-4", active && "text-gold")} />
              {item.label}
            </Link>
          );
        })}
        <button
          onClick={() => setMobileOpen(true)}
          className="flex min-h-12 flex-col items-center justify-center gap-1 rounded-xl text-[.54rem] font-bold text-white/45"
        >
          <Menu className="size-4" />
          More
        </button>
      </nav>
      {commandOpen && (
        <div
          className="fixed inset-0 z-[80] flex items-start justify-center bg-black/40 px-4 pt-[12vh] backdrop-blur-sm"
          onMouseDown={() => setCommandOpen(false)}
        >
          <div
            onMouseDown={(event) => event.stopPropagation()}
            className="w-full max-w-xl overflow-hidden rounded-[1.4rem] border border-line bg-panel shadow-2xl"
          >
            <div className="flex items-center gap-3 border-b border-line px-5">
              <Search className="size-5 text-muted" />
              <input
                autoFocus
                value={commandQuery}
                onChange={(event) => setCommandQuery(event.target.value)}
                placeholder="Go to a workspace…"
                className="min-h-16 w-full bg-transparent text-sm outline-none"
              />
              <button
                onClick={() => setCommandOpen(false)}
                className="text-xs text-muted"
              >
                ESC
              </button>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              {commandItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setCommandOpen(false)}
                    className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-bold hover:bg-ink/5"
                  >
                    <Icon className="size-4 text-coral" />
                    {item.label}
                    <Command className="ml-auto size-3 text-muted" />
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
