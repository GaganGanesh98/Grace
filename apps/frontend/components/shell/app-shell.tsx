"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  ChevronDown,
  ChevronRight,
  FolderKanban,
  KeyRound,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactElement, type ReactNode } from "react";

import { ConnectionIndicator } from "@/components/command-center/connection-indicator";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { Button } from "@/components/ui/button";
import { apiLogout, apiMe } from "@/lib/api";
import { cn } from "@/lib/utils";

import { CommandPalette } from "./command-palette";
import { breadcrumbFor, isNavActive, navGroups } from "./nav-config";
import { ProjectSwitcher } from "./project-switcher";
import { ThemeToggle } from "./theme-toggle";

const COLLAPSE_KEY = "grace-sidebar-collapsed";

// Desktop sidebar collapse is a per-browser preference kept in localStorage.
// Storage can be unavailable (private mode, blocked site data), so every access
// is guarded and the sidebar simply defaults to expanded.
const collapseListeners = new Set<() => void>();

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeCollapsed(value: boolean): void {
  try {
    window.localStorage.setItem(COLLAPSE_KEY, value ? "1" : "0");
  } catch {
    // non-essential preference
  }
  collapseListeners.forEach((notify) => notify());
}

function subscribeCollapsed(notify: () => void): () => void {
  collapseListeners.add(notify);
  return () => collapseListeners.delete(notify);
}

function Logo({ compact }: { compact: boolean }): ReactElement {
  return (
    <Link href="/dashboard" className="flex h-[38px] min-w-0 items-center gap-2.5 rounded-md px-[5px] outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
      <span
        className="grid size-[30px] shrink-0 place-items-center rounded-md bg-[linear-gradient(135deg,var(--primary),var(--info))] text-[14px] font-extrabold text-primary-foreground shadow-[0_0_24px_color-mix(in_oklab,var(--primary)_28%,transparent)]"
        aria-hidden
      >
        G
      </span>
      <span className={cn("min-w-0 leading-tight", compact && "sr-only")}>
        <strong className="block text-[15px] font-semibold text-foreground">Grace</strong>
        <small className="block text-[10px] text-muted-foreground">Governance OS</small>
      </span>
    </Link>
  );
}

function initialsFor(name: string | null | undefined, email: string | undefined): string {
  const source = name?.trim() || email?.split("@")[0] || "";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
  return letters.toUpperCase() || "?";
}

function UserBlock({ compact }: { compact: boolean }): ReactElement {
  const { data: me } = useQuery({
    queryKey: ["axiom", "me"],
    queryFn: () => apiMe(),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });
  const displayName = me?.full_name?.trim() || me?.email?.split("@")[0] || "—";

  return (
    <div className={cn("flex min-w-0 items-center gap-2.5 border-t border-border px-[5px] pt-3.5", compact && "flex-col")}>
      <span
        className="grid size-[30px] shrink-0 place-items-center overflow-hidden rounded-full bg-accent text-[11px] font-bold text-accent-foreground"
        aria-hidden
      >
        {me?.avatar_url ? (
          // User-provided URL; next/image would need a host allowlist. Small avatar, fine for LCP.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={me.avatar_url} alt="" className="size-[30px] object-cover" />
        ) : (
          initialsFor(me?.full_name, me?.email)
        )}
      </span>
      <div className={cn("min-w-0 flex-1", compact && "sr-only")}>
        <strong className="block truncate text-[12px] font-semibold text-foreground">{displayName}</strong>
        <span className="mt-0.5 block truncate text-[11px] text-muted-foreground" title={me?.email}>
          {me?.email ?? ""}
        </span>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Sign out"
        title="Sign out"
        onClick={() => {
          void apiLogout().then(() => {
            // A full page load (not router.push) deliberately drops every cached
            // query and in-memory workspace state belonging to the old session.
            // eslint-disable-next-line @next/next/no-location-assign-relative-destination
            window.location.href = "/login";
          });
        }}
      >
        <LogOut aria-hidden />
      </Button>
    </div>
  );
}

function NewMenu({ newAgentHref }: { newAgentHref: string }): ReactElement {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onDocClick(e: MouseEvent): void {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent): void {
      if (e.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const items = [
    { href: "/dashboard/projects", label: "New project", icon: FolderKanban },
    { href: newAgentHref, label: "New agent", icon: Bot },
    { href: "/dashboard/vault", label: "Add credential", icon: KeyRound },
  ];

  return (
    <div ref={rootRef} className="relative">
      <Button
        type="button"
        variant="primary"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Create new"
        className="max-sm:w-9 max-sm:px-0"
        onClick={() => setOpen((o) => !o)}
      >
        <Plus aria-hidden />
        <span className="max-sm:hidden">New</span>
        <ChevronDown className="max-sm:hidden" aria-hidden />
      </Button>
      {open ? (
        <div
          role="menu"
          aria-label="Create new"
          className="absolute right-0 top-11 z-50 w-[180px] rounded-md border border-border bg-popover p-[5px] shadow-[var(--shadow-panel)]"
        >
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                role="menuitem"
                href={item.href}
                className="flex items-center gap-2.5 rounded-sm p-[9px] text-[13px] text-popover-foreground outline-none hover:bg-secondary focus-visible:bg-secondary"
                onClick={() => setOpen(false)}
              >
                <Icon className="size-4 text-muted-foreground" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Phase 8.3 application shell — the Lovable "Grace" design (grouped sidebar,
 * sticky topbar, ⌘K palette, theme toggle) wired to real workspace, user and
 * route data.
 */
export function AppShell({ children }: { children: ReactNode }): ReactElement {
  const pathname = usePathname();
  const { projects, activeProjectId } = useProjectWorkspace();
  const collapsed = useSyncExternalStore(subscribeCollapsed, readCollapsed, () => false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Close the mobile drawer whenever the route changes (including back/forward).
  const [drawerPath, setDrawerPath] = useState(pathname);
  if (drawerPath !== pathname) {
    setDrawerPath(pathname);
    setMobileOpen(false);
  }

  // Agent creation lives inside a project; /dashboard/agents is a placeholder.
  const newAgentHref = activeProjectId
    ? `/dashboard/projects/${activeProjectId}/agent-definitions`
    : "/dashboard/projects";

  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (e.key === "Escape") {
        setMobileOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const toggleCollapsed = (): void => writeCollapsed(!collapsed);

  // The mobile drawer always shows labels; "collapsed" is a desktop-only mode.
  const compact = collapsed && !mobileOpen;
  const crumbs = breadcrumbFor(pathname, (segment) => projects.find((p) => p.id === segment)?.name);

  return (
    <div className="min-h-screen bg-background font-[family-name:var(--font-sans)] text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[200] focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>

      <aside
        aria-label="Primary"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[260px] flex-col border-r border-border bg-[var(--sidebar-bg)] px-3 py-[18px] transition-[width,transform] duration-200 ease-out motion-reduce:transition-none",
          mobileOpen ? "translate-x-0 shadow-[0_0_50px_rgb(0_0_0/0.4)]" : "-translate-x-full",
          "md:translate-x-0 md:shadow-none",
          compact ? "md:w-[72px]" : "md:w-[240px]",
        )}
      >
        <div className="flex items-center justify-between">
          <Logo compact={compact} />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Close navigation"
            className="md:hidden"
            onClick={() => setMobileOpen(false)}
          >
            <X aria-hidden />
          </Button>
        </div>

        <div className="mx-0.5 mb-3.5 mt-[18px]">
          <ProjectSwitcher collapsed={compact} onNavigated={() => setMobileOpen(false)} />
        </div>

        <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
          {navGroups.map((group) => (
            <section key={group.label} className="mt-3.5 first:mt-0">
              <p
                className={cn(
                  "mx-2.5 mb-[7px] text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground",
                  compact && "sr-only",
                )}
              >
                {group.label}
              </p>
              <ul className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const active = isNavActive(item, pathname);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        title={compact ? item.label : undefined}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex h-[38px] items-center gap-[11px] whitespace-nowrap rounded-[7px] px-2.5 text-[13px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                          compact && "justify-center px-0",
                          active
                            ? "bg-accent font-semibold text-accent-foreground"
                            : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                        )}
                      >
                        <Icon className="size-[17px] shrink-0" aria-hidden />
                        <span className={cn("truncate", compact && "sr-only")}>{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </nav>

        <ConnectionIndicator />
        <UserBlock compact={compact} />
      </aside>

      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-[35] bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <div
        className={cn(
          "min-w-0 transition-[padding] duration-200 ease-out motion-reduce:transition-none",
          compact ? "md:pl-[72px]" : "md:pl-[240px]",
        )}
      >
        <header className="sticky top-0 z-30 flex h-[58px] items-center justify-between gap-3 border-b border-border bg-[color:color-mix(in_oklab,var(--background)_88%,transparent)] px-3.5 backdrop-blur-[18px] sm:h-16 md:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Open navigation"
              aria-expanded={mobileOpen}
              className="md:hidden"
              onClick={() => setMobileOpen(true)}
            >
              <Menu aria-hidden />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="max-md:hidden"
              onClick={toggleCollapsed}
            >
              {collapsed ? <PanelLeftOpen aria-hidden /> : <PanelLeftClose aria-hidden />}
            </Button>
            <nav aria-label="Breadcrumb" className="min-w-0">
              <ol className="flex min-w-0 items-center gap-1 text-[13px] text-muted-foreground">
                {crumbs.map((crumb, i) => {
                  const last = i === crumbs.length - 1;
                  return (
                    <li
                      key={`${crumb.href}-${i}`}
                      className={cn("flex min-w-0 items-center gap-1", !last && "max-sm:hidden")}
                    >
                      {i > 0 ? <ChevronRight className="size-[13px] shrink-0 max-sm:hidden" aria-hidden /> : null}
                      {last ? (
                        <span
                          aria-current="page"
                          className={cn("truncate font-semibold text-foreground", crumb.mono && "font-mono text-[12px]")}
                        >
                          {crumb.label}
                        </span>
                      ) : (
                        <Link
                          href={crumb.href}
                          className={cn("truncate rounded-xs hover:text-foreground", crumb.mono && "font-mono text-[12px]")}
                        >
                          {crumb.label}
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
          </div>

          <div className="flex shrink-0 items-center gap-0.5 sm:gap-2">
            <button
              type="button"
              aria-label="Search (⌘K)"
              className="flex h-9 w-9 items-center justify-center gap-2 rounded-md border border-border bg-secondary text-[13px] text-muted-foreground outline-none transition-colors hover:border-[var(--border-emphasis)] focus-visible:border-[var(--ring)] focus-visible:ring-[3px] focus-visible:ring-[color:color-mix(in_oklab,var(--ring)_28%,transparent)] sm:w-[180px] sm:justify-start sm:px-2.5 xl:w-60"
              onClick={() => setPaletteOpen(true)}
            >
              <Search className="size-4 shrink-0" aria-hidden />
              <span className="flex-1 text-left max-xl:hidden">Search anything</span>
              <kbd className="rounded-xs border border-border bg-[var(--surface-raised)] px-[5px] py-0.5 font-[family-name:var(--font-sans)] text-[11px] max-sm:hidden sm:ml-auto">
                ⌘K
              </kbd>
            </button>
            <ThemeToggle />
            <NewMenu newAgentHref={newAgentHref} />
          </div>
        </header>

        <main id="main-content" className="min-w-0 px-4 py-6 sm:px-6 md:px-8 md:py-7">
          <div className="mx-auto max-w-[min(100%,1400px)]">{children}</div>
        </main>
      </div>

      {paletteOpen ? <CommandPalette onClose={() => setPaletteOpen(false)} newAgentHref={newAgentHref} /> : null}
    </div>
  );
}
