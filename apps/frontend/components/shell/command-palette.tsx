"use client";

import { ArrowRight, FolderKanban, Plus, Search, type LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactElement } from "react";

import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { cn } from "@/lib/utils";

import { navItems } from "./nav-config";

type Command = {
  id: string;
  group: "Pages" | "Create" | "Projects";
  label: string;
  icon: LucideIcon;
  run: () => void;
};

/** Mounted only while open, so the query and cursor start fresh each time. */
export function CommandPalette({
  onClose,
  newAgentHref,
}: {
  onClose: () => void;
  newAgentHref: string;
}): ReactElement {
  const router = useRouter();
  const { projects, setActiveProjectId } = useProjectWorkspace();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  const commands = useMemo<Command[]>(() => {
    const go = (href: string) => () => router.push(href);
    return [
      ...navItems.map((i) => ({ id: i.href, group: "Pages" as const, label: i.label, icon: i.icon, run: go(i.href) })),
      { id: "new-project", group: "Create", label: "New project", icon: Plus, run: go("/dashboard/projects") },
      { id: "new-agent", group: "Create", label: "New agent", icon: Plus, run: go(newAgentHref) },
      { id: "new-credential", group: "Create", label: "Add credential", icon: Plus, run: go("/dashboard/vault") },
      ...projects.map((p) => ({
        id: `project-${p.id}`,
        group: "Projects" as const,
        label: p.name,
        icon: FolderKanban,
        run: () => {
          setActiveProjectId(p.id);
          router.push(`/dashboard/projects/${p.id}`);
        },
      })),
    ];
  }, [router, newAgentHref, projects, setActiveProjectId]);

  const q = query.trim().toLowerCase();
  const results = q ? commands.filter((c) => c.label.toLowerCase().includes(q)) : commands;

  useEffect(() => {
    // Return focus to whatever opened the palette (the search button, or the
    // element focused when ⌘K was pressed).
    const previous = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => previous?.focus();
  }, []);

  const select = (c: Command | undefined): void => {
    if (!c) {
      return;
    }
    onClose();
    c.run();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      select(results[cursor]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  const activeId = results[cursor] ? `${listId}-${results[cursor].id}` : undefined;

  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-start justify-center bg-black/60 px-4 pt-[12vh] backdrop-blur-[3px]"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="w-[min(620px,calc(100vw-32px))] overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-[0_24px_80px_rgb(0_0_0/0.45)]"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-3.5">
          <Search className="size-[18px] text-muted-foreground" aria-hidden />
          <input
            ref={inputRef}
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={activeId}
            aria-autocomplete="list"
            placeholder="Search pages, projects, actions…"
            className="flex-1 bg-transparent text-[14px] text-foreground outline-none placeholder:text-muted-foreground"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setCursor(0);
            }}
            onKeyDown={onKeyDown}
          />
          <kbd className="rounded-xs border border-border bg-[var(--surface-raised)] px-1.5 py-0.5 text-[11px] text-muted-foreground">
            Esc
          </kbd>
        </div>
        <ul id={listId} role="listbox" aria-label="Results" className="max-h-[50vh] overflow-y-auto p-1.5">
          {results.length === 0 ? (
            <li className="px-3 py-6 text-center text-[13px] text-muted-foreground">No matches</li>
          ) : null}
          {results.map((c, i) => {
            const Icon = c.icon;
            const showGroup = i === 0 || results[i - 1].group !== c.group;
            return (
              <li key={c.id} role="presentation">
                {showGroup ? (
                  <p className="px-2.5 pb-1 pt-2 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground">
                    {c.group}
                  </p>
                ) : null}
                <div
                  id={`${listId}-${c.id}`}
                  role="option"
                  aria-selected={i === cursor}
                  className={cn(
                    "grid cursor-pointer grid-cols-[20px_1fr_16px] items-center gap-2.5 rounded-md px-2.5 py-2.5 text-[13px] text-foreground",
                    i === cursor && "bg-secondary",
                  )}
                  onMouseMove={() => setCursor(i)}
                  onClick={() => select(c)}
                >
                  <Icon className="size-4 text-muted-foreground" aria-hidden />
                  <span className="truncate">{c.label}</span>
                  <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
