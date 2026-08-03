"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactElement } from "react";

import { useProjectWorkspace } from "@/components/project-workspace-provider";

export default function AgentDetailPlaceholderPage(): ReactElement {
  const p = useParams<{ agentId: string }>();
  const { activeProjectId } = useProjectWorkspace();
  const agentId = p.agentId;

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-axiom-18">Agent</h1>
      <p className="text-[var(--axiom-text-muted)]">Detail view (Phase 7.9) — id {agentId}</p>
      {activeProjectId ? (
        <Link href={`/dashboard/projects/${activeProjectId}/agents`} className="text-[var(--axiom-electric)]">
          Back to project agents
        </Link>
      ) : null}
    </div>
  );
}
