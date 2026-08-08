"use client";

import {
  Bot,
  FileText,
  Folder,
  KeyRound,
  LayoutGrid,
  Menu,
  ScrollText,
  Settings,
  Shield,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";

import { ConnectionIndicator } from "@/components/command-center/connection-indicator";
import { Button } from "@/components/ui/button";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { apiLogout, apiMe } from "@/lib/api";
import { cn } from "@/lib/utils";

const mainNav = [
  { href: "/dashboard", label: "Command center", icon: LayoutGrid, end: true as const },
  { href: "/dashboard/projects", label: "Projects", icon: Folder, end: false as const },
  { href: "/dashboard/agents", label: "Agents", icon: Bot, end: false as const },
  { href: "/dashboard/vault", label: "Vault", icon: KeyRound, end: false as const },
  { href: "/dashboard/receipts", label: "Receipts", icon: FileText, end: false as const },
  { href: "/dashboard/ledger", label: "Governance ledger", icon: ScrollText, end: false as const },
  { href: "/dashboard/policies", label: "Policies", icon: Shield, end: false as const },
  { href: "/dashboard/settings", label: "Settings", icon: Settings, end: false as const },
] as const;

function isNavActive(
  href: (typeof mainNav)[number]["href"],
  end: (typeof mainNav)[number]["end"],
  pathname: string,
): boolean {
  if (end) {
    return pathname === "/dashboard" || pathname === "/dashboard/";
  }
  if (href === "/dashboard/ledger") {
    return pathname === "/dashboard/ledger" || pathname.startsWith("/dashboard/ledger/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Wordmark(): ReactElement {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-[22px] w-[22px] shrink-0 items-center justify-center">
        <div className="flex h-[22px] w-[22px] rotate-45 items-center justify-center border border-text-primary bg-transparent text-text-primary">
          <div className="h-1.5 w-1.5 -rotate-45 bg-current" />
        </div>
      </div>
      <span className="font-mono text-axiom-13 font-semibold uppercase tracking-[3px] text-text-primary">
        Grace
      </span>
    </div>
  );
}

function ProjectSwitcher({ onNavigated }: { onNavigated: () => void }): ReactElement {
  const router = useRouter();
  const { projects, projectsLoading, activeProjectId, activeProject, setActiveProjectId } =
    useProjectWorkspace();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent): void {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  if (projectsLoading) {
    return (
      <div
        className="mt-4 h-9 animate-pulse rounded-md border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)]"
        role="status"
        aria-label="Loading projects"
      />
    );
  }

  if (projects.length === 0) {
    return (
      <Link
        href="/dashboard/projects"
        className="mt-4 block rounded-md border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] px-3 py-2 font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-text-dim)] transition hover:border-[var(--axiom-electric)]/30 hover:text-[var(--axiom-text-muted)]"
        onClick={onNavigated}
      >
        No project
      </Link>
    );
  }

  const label = activeProject?.name ?? "Project";

  if (projects.length === 1) {
    return (
      <div className="mt-4 space-y-2">
        <div className="rounded-md border border-[var(--axiom-border-strong)] bg-[var(--axiom-bg-card)] px-3 py-2 font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-text-muted)]">
          {label}
        </div>
        <Link
          href="/dashboard/projects"
          className="block font-mono text-axiom-11 uppercase tracking-wide text-[var(--axiom-electric)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--axiom-electric)]/40"
          onClick={onNavigated}
        >
          MANAGE PROJECTS
        </Link>
      </div>
    );
  }

  return (
    <div ref={rootRef} className="relative mt-4">
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
        }}
        className="flex w-full items-center justify-between gap-2 rounded-md border border-[var(--axiom-electric)]/30 bg-[var(--axiom-bg-card)] px-3 py-2 text-left font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-text)] transition hover:border-[var(--axiom-electric)]/50"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className="min-w-0 truncate">{label}</span>
        <span className="text-[var(--axiom-text-dim)]" aria-hidden>
          ▾
        </span>
      </button>
      {open ? (
        <ul
          className="absolute left-0 right-0 z-50 mt-1 max-h-64 overflow-auto rounded-md border border-[var(--axiom-electric)]/20 bg-[var(--axiom-bg-card)] py-1 shadow-lg"
          role="listbox"
        >
          {projects.map((p) => (
            <li key={p.id} role="option" aria-selected={p.id === activeProjectId}>
              <button
                type="button"
                className={cn(
                  "w-full px-3 py-2 text-left font-mono text-axiom-12 uppercase tracking-wide",
                  p.id === activeProjectId
                    ? "bg-surface-elevated font-semibold text-text-primary"
                    : "text-[var(--axiom-text-muted)] hover:bg-[rgba(255,255,255,0.04)]",
                )}
                onClick={() => {
                  setOpen(false);
                  onNavigated();
                  if (p.id !== activeProjectId) {
                    setActiveProjectId(p.id);
                  }
                }}
              >
                {p.name}
              </button>
            </li>
          ))}
          <li className="border-t border-[var(--axiom-border)] pt-1">
            <button
              type="button"
              className="w-full px-3 py-2 text-left font-mono text-axiom-11 uppercase tracking-wide text-[var(--axiom-electric)] outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--axiom-electric)]/40"
              onClick={() => {
                setOpen(false);
                onNavigated();
                router.push("/dashboard/projects");
              }}
            >
              MANAGE PROJECTS
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}

/**
 * 7.5.2 command center shell navigation (~224px), quick actions, user block. Used by the dashboard layout.
 */
export function CommandCenterSidebar(): ReactElement {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const router = useRouter();

  const { data: me } = useQuery({
    queryKey: ["axiom", "me"],
    queryFn: () => apiMe(),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  const displayEmail = me?.email ?? "—";
  const initial = (me?.email?.trim().charAt(0) || "?").toUpperCase();

  return (
    <>
      <div className="fixed left-4 top-4 z-50 md:hidden">
        <Button
          type="button"
          size="icon-sm"
          variant="secondary"
          className="border border-[var(--axiom-electric)]/20 bg-[var(--axiom-bg-card)]"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => {
            setOpen(!open);
          }}
        >
          {open ? <X className="h-4 w-4" aria-hidden /> : <Menu className="h-4 w-4" aria-hidden />}
        </Button>
      </div>
      {open ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
          onClick={() => {
            setOpen(false);
          }}
        />
      ) : null}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-56 min-w-56 max-w-56 flex-col border-r border-[var(--axiom-border)] bg-[var(--axiom-bg-alt)] pt-14 transition-transform duration-200 md:relative md:translate-x-0 md:pt-0",
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
        aria-label="Command center"
      >
        <div className="border-b border-[var(--axiom-border)] px-5 py-5">
          <Wordmark />
          <p className="mt-2 font-mono text-axiom-10 uppercase tracking-[1.5px] text-[var(--axiom-text-label)]">
            Command center
          </p>
          <ProjectSwitcher onNavigated={() => setOpen(false)} />
        </div>
        <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-3" aria-label="Main">
          {mainNav.map((item) => {
            const active = isNavActive(item.href, item.end, pathname);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => {
                  setOpen(false);
                }}
                className={cn(
                  "flex min-h-[40px] items-center gap-3 rounded-md border border-transparent py-2.5 pl-3 pr-2 font-mono text-axiom-12 transition",
                  active
                    ? "border-l-[3px] border-l-text-primary bg-surface-elevated pl-[9px] font-semibold text-text-primary"
                    : "text-[var(--axiom-text-muted)] hover:bg-[rgba(255,255,255,0.04)]",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className="min-w-0 truncate text-axiom-12">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-[var(--axiom-border)] px-3 py-2">
          <p className="px-1 font-mono text-axiom-10 uppercase tracking-wider text-[var(--axiom-text-label)]">
            Quick actions
          </p>
          <div className="mt-1.5 flex flex-col gap-1.5">
            <Button
              type="button"
              className="w-full justify-center text-axiom-12"
              variant="primary"
              onClick={() => {
                setOpen(false);
                router.push("/dashboard/projects");
              }}
            >
              + NEW PROJECT
            </Button>
            <Button
              type="button"
              variant="primary"
              className="w-full justify-center text-axiom-12"
              onClick={() => {
                setOpen(false);
                router.push("/dashboard/agents");
              }}
            >
              + NEW AGENT
            </Button>
            <Button
              type="button"
              variant="primary"
              className="w-full justify-center text-axiom-12"
              onClick={() => {
                setOpen(false);
                router.push("/dashboard/vault");
              }}
            >
              + ADD CREDENTIAL
            </Button>
          </div>
        </div>
        <ConnectionIndicator />
        <div className="border-t border-[var(--axiom-border)] p-3">
          <div className="flex min-h-[40px] items-center gap-3 rounded-md p-1">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--axiom-border)] bg-[var(--axiom-bg)] font-mono text-axiom-12 text-[var(--axiom-electric)]"
              aria-hidden
            >
              {me?.avatar_url ? (
                // User-provided URL; next/image would require allowlist; small avatar, ok for LCP
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={me.avatar_url}
                  alt=""
                  className="h-9 w-9 rounded-full object-cover"
                />
              ) : (
                initial
              )}
            </div>
            <div className="min-w-0 flex-1 text-left">
              <p className="truncate font-mono text-axiom-12 text-[var(--axiom-text)]">{displayEmail}</p>
              <button
                type="button"
                className="text-axiom-11 text-[var(--axiom-electric)] underline-offset-2 hover:underline"
                onClick={() => {
                  void apiLogout().then(() => {
                    window.location.href = "/login";
                  });
                }}
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
