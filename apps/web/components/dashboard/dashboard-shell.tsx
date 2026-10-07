"use client";

import { useQuery } from "@tanstack/react-query";
import { Command, LogOut, Menu, Moon, Search, Sun, X } from "lucide-react";
import { useTheme } from "next-themes";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Logo } from "@/components/logo";
import { ActivePollPrompt } from "@/components/dashboard/active-poll-prompt";
import { NotificationBell } from "@/components/dashboard/notification-bell";
import { useRealtime } from "@/components/realtime-provider";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  isNavigationHrefActive,
  navigation,
  navigationItemForPath,
} from "@/lib/navigation";
import { cn, initials } from "@/lib/utils";

type User = {
  id: string;
  full_name: string;
  email: string;
  profile_media_id: string | null;
  must_change_password: boolean;
  must_complete_executive_profile: boolean;
  roles: string[];
  permissions: string[];
};

function LiveState() {
  const { state } = useRealtime();
  const label =
    state === "live"
      ? "Workspace is live"
      : state === "connecting"
        ? "Reconnecting to the workspace"
        : "Workspace is offline";
  return (
    <span title={label} className="grid size-10 place-items-center text-muted">
      <span
        className={cn(
          "size-1.5 rounded-full",
          state === "live"
            ? "animate-pulse bg-emerald-500"
            : state === "connecting"
              ? "animate-pulse bg-gold"
              : "bg-muted/70",
        )}
      />
      <span className="sr-only">{label}</span>
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
  const commandDialogRef = useRef<HTMLDivElement>(null);
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
      return;
    }
    if (
      user.data?.must_complete_executive_profile &&
      !user.data.must_change_password &&
      pathname !== "/dashboard/profile"
    ) {
      router.replace("/dashboard/profile?executive=required");
    }
  }, [
    pathname,
    router,
    user.data?.must_change_password,
    user.data?.must_complete_executive_profile,
  ]);
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
  useEffect(() => {
    if (!commandOpen) return;
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const handleDialogKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setCommandOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const controls = Array.from(
        commandDialogRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      if (!controls.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", handleDialogKeyDown);
    return () => {
      window.removeEventListener("keydown", handleDialogKeyDown);
      previousFocus?.focus();
    };
  }, [commandOpen]);
  const items = useMemo(
    () =>
      navigation.filter(
        (item) => !user.data || user.data.permissions.includes(item.permission),
      ),
    [user.data],
  );
  const groups = [...new Set(items.map((item) => item.group))];
  const current = navigationItemForPath(items, pathname);
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
                  const active = isNavigationHrefActive(item.href, pathname);
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
    <div className="dashboard-canvas min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-[17rem] flex-col bg-[#091529] lg:flex">
        {sidebar}
      </aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            className="absolute inset-0 bg-ink/20"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation backdrop"
          />
          <aside className="relative flex h-full w-[min(19rem,88vw)] flex-col bg-[#091529] shadow-2xl">
            {sidebar}
          </aside>
        </div>
      )}
      <div className="lg:pl-[17rem]">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-line/55 bg-paper/62 px-4 backdrop-blur-2xl sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              className="grid size-10 place-items-center rounded-full text-ink lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="size-5" />
            </button>
            <div className="min-w-0">
              <p className="eyebrow text-muted/80">
                {user.data?.permissions.includes("settings.manage")
                  ? "Admin workspace"
                  : user.data?.permissions.includes("members.view")
                    ? "Executive workspace"
                    : "Member workspace"}
              </p>
              <h1 className="mt-0.5 truncate text-sm font-semibold tracking-tight text-ink/75">
                {current?.label ?? "Dashboard"}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-0.5">
            <span className="hidden sm:inline-flex">
              <LiveState />
            </span>
            <button
              onClick={() => setCommandOpen(true)}
              className="grid size-10 place-items-center rounded-full text-muted transition hover:bg-ink/5 hover:text-ink"
              aria-label="Search workspaces"
            >
              <Search className="size-4" />
            </button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() =>
                setTheme(resolvedTheme === "dark" ? "light" : "dark")
              }
              aria-label="Toggle theme"
            >
              <Sun className="hidden size-4 dark:block" />
              <Moon className="size-4 dark:hidden" />
            </Button>
            <NotificationBell enabled={Boolean(user.data)} />
            <Link
              href="/dashboard/profile"
              className="ml-1 grid size-10 place-items-center rounded-full transition hover:bg-ink/5"
              aria-label="Open profile"
            >
              <span className="relative grid size-8 place-items-center overflow-hidden rounded-full bg-ink text-[.65rem] font-bold text-paper">
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
            </Link>
          </div>
        </header>
        <main
          id="main-content"
          className="mx-auto max-w-[105rem] px-4 py-4 pb-[calc(7rem+env(safe-area-inset-bottom))] sm:px-6 sm:py-5 lg:px-8 lg:pb-8"
        >
          {children}
        </main>
      </div>
      <nav
        aria-label="Dashboard navigation"
        data-dashboard-bottom-nav
        className="fixed right-3 left-3 z-40 grid grid-cols-5 rounded-[1.25rem] border border-white/10 bg-[#091529]/95 p-1.5 shadow-2xl backdrop-blur-xl [bottom:calc(0.75rem+env(safe-area-inset-bottom))] lg:hidden"
      >
        {items.slice(0, 4).map((item) => {
          const Icon = item.icon;
          const active = isNavigationHrefActive(item.href, pathname);
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
          className="fixed inset-0 z-[80] flex items-start justify-center bg-ink/20 px-4 pt-[12vh]"
          onMouseDown={() => setCommandOpen(false)}
          role="presentation"
        >
          <div
            ref={commandDialogRef}
            role="dialog"
            aria-modal="true"
            aria-label="Workspace search"
            onMouseDown={(event) => event.stopPropagation()}
            className="workspace-folio w-full max-w-xl overflow-hidden rounded-[1.4rem]"
          >
            <div className="flex items-center gap-3 border-b border-line px-5">
              <Search className="size-5 text-muted" />
              <input
                autoFocus
                value={commandQuery}
                onChange={(event) => setCommandQuery(event.target.value)}
                placeholder="Go to a workspace…"
                aria-label="Search workspaces"
                className="min-h-16 w-full bg-transparent text-sm outline-none"
              />
              <button
                onClick={() => setCommandOpen(false)}
                aria-label="Close workspace search"
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
      {user.data ? (
        <ActivePollPrompt
          enabled={Boolean(
            !user.data.must_change_password &&
            !user.data.must_complete_executive_profile,
          )}
          pathname={pathname}
          userId={user.data.id}
        />
      ) : null}
    </div>
  );
}
