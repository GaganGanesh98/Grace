"use client";

import Link from "next/link";
import type { ReactElement } from "react";

import { Button } from "@/components/ui/button";
import type { AgentDefinitionOut } from "@/lib/types";
import { cn } from "@/lib/utils";

type AgentListProps = {
  projectId: string;
  definitions: AgentDefinitionOut[];
  onArchive: (id: string) => void;
  archivingId: string | null;
};

export function AgentList({
  projectId,
  definitions,
  onArchive,
  archivingId,
}: AgentListProps): ReactElement {
  if (definitions.length === 0) {
    return (
      <p className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0A0A14] p-6 font-mono text-axiom-13 uppercase tracking-wide text-[#6B7490]">
        No agents yet.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {definitions.map((d) => (
        <li
          key={d.id}
          className={cn(
            "flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0A0A14] px-4 py-3",
            d.is_archived && "opacity-60",
          )}
        >
          <Link
            href={`/dashboard/projects/${projectId}/agent-definitions/${d.id}`}
            aria-label={d.name}
            className={cn(
              "min-w-0 flex-1 rounded-md py-0.5 outline-none transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2",
              !d.is_archived && "hover:bg-[rgba(255,255,255,0.03)]",
            )}
          >
            <div className="font-mono text-axiom-15 font-medium text-[var(--axiom-electric)] underline-offset-2 hover:underline">
              {d.name}
            </div>
            <p className="mt-1 font-mono text-axiom-12 text-[#A0A8BC]">{d.model}</p>
            {d.is_archived ? (
              <p className="mt-1 font-mono text-axiom-11 uppercase text-[#6B7490]">Archived</p>
            ) : null}
          </Link>
          {!d.is_archived ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={archivingId === d.id}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onArchive(d.id);
              }}
            >
              Archive
            </Button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
