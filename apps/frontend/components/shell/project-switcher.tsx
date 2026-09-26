"use client";

import { ChevronDown, FolderKanban } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactElement } from "react";

import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { cn } from "@/lib/utils";

const TRIGGER =
  "flex h-[38px] w-full items-center gap-2.5 rounded-md border border-border bg-[var(--surface-raised)] px-[11px] text-left text-[13px] text-foreground outline-none transition-colors focus-visible:border-[var(--ring)] focus-visible:ring-[3px] focus-visible:ring-[color:color-mix(in_oklab,var(--ring)_28%,transparent)]";

function StatusDot(): ReactElement {
  return (
    <span
      className="inline-block size-[7px] shrink-0 rounded-full bg-[var(--success)] shadow-[0_0_0_3px_color-mix(in_oklab,var(--success)_14%,transparent)]"
      aria-hidden
    />
  );
}

/** Active-project picker backed by ProjectWorkspaceProvider (real projects, not the export's mock). */
export function ProjectSwitcher({
  collapsed,
  onNavigated,
}: {
  collapsed: boolean;
  onNavigated: () => void;
}): ReactElement {
  const router = useRouter();
  const { projects, projectsLoading, activeProjectId, activeProject, setActiveProjectId } = useProjectWorkspace();
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

  if (projectsLoading) {
    return (
      <div
        className="h-[38px] animate-pulse rounded-md border border-border bg-secondary"
        role="status"
        aria-label="Loading projects"
      />
    );
  }

  if (projects.length === 0) {
    return (
      <Link
        href="/dashboard/projects"
        className={cn(TRIGGER, "text-muted-foreground hover:border-[var(--border-emphasis)]", collapsed && "justify-center px-0")}
        title="No project — create one"
        onClick={onNavigated}
      >
        <FolderKanban className="size-3.5 shrink-0" aria-hidden />
        {collapsed ? null : <span className="truncate">No project yet</span>}
      </Link>
    );
  }

  const label = activeProject?.name ?? "Select project";

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className={cn(TRIGGER, "hover:border-[var(--border-emphasis)]", collapsed && "justify-center px-0")}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={collapsed ? `Project: ${label}` : undefined}
        title={label}
        onClick={() => setOpen((o) => !o)}
      >
        <StatusDot />
        {collapsed ? null : (
          <>
            <span className="min-w-0 flex-1 truncate">{label}</span>
            <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          </>
        )}
      </button>
      {open ? (
        <ul
          role="listbox"
          aria-label="Projects"
          className={cn(
            "absolute top-[calc(100%+4px)] z-50 max-h-64 overflow-auto rounded-md border border-border bg-popover p-1 shadow-[var(--shadow-panel)]",
            collapsed ? "left-0 w-56" : "inset-x-0",
          )}
        >
          {projects.map((p) => (
            <li key={p.id} role="option" aria-selected={p.id === activeProjectId}>
              <button
                type="button"
                className={cn(
                  "w-full truncate rounded-sm px-2.5 py-2 text-left text-[13px]",
                  p.id === activeProjectId
                    ? "bg-accent font-semibold text-accent-foreground"
                    : "text-foreground hover:bg-secondary",
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
          <li className="mt-1 border-t border-border pt-1">
            <button
              type="button"
              className="w-full rounded-sm px-2.5 py-2 text-left text-[12px] font-medium text-accent-foreground hover:bg-secondary"
              onClick={() => {
                setOpen(false);
                onNavigated();
                router.push("/dashboard/projects");
              }}
            >
              Manage projects
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}
