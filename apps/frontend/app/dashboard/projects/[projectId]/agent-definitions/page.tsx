"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState, type ReactElement } from "react";
import { toast } from "sonner";

import { AgentForm } from "@/components/agent-definitions/agent-form";
import { AgentList } from "@/components/agent-definitions/agent-list";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { useAgentDefinitions, useArchiveAgentDefinition, useCreateAgentDefinition } from "@/hooks/use-agent-definitions";
import { listVaultKeys } from "@/lib/vault-api";

export default function AgentDefinitionsPage(): ReactElement {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const { projects } = useProjectWorkspace();
  const projectName = useMemo(
    () => projects.find((p) => p.id === projectId)?.name ?? "Project",
    [projects, projectId],
  );

  const defs = useAgentDefinitions(projectId);
  const vault = useQuery({
    queryKey: ["axiom", "vault-keys", "llm"],
    queryFn: () => listVaultKeys({ kind: "llm" }),
  });
  const createDef = useCreateAgentDefinition(projectId);
  const archive = useArchiveAgentDefinition(projectId);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [archivingId, setArchivingId] = useState<string | null>(null);

  return (
    <div className="space-y-10">
      <div>
        <Link
          href="/dashboard/projects"
          className="font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-electric)] hover:underline"
        >
          ← Projects
        </Link>
        <p className="mt-4 font-mono text-axiom-11 uppercase tracking-[2px] text-[#6B7490]">Agents</p>
        <h1 className="mt-2 font-mono text-axiom-22 font-medium uppercase tracking-wide text-[#F0F2F8]">
          {projectName}
        </h1>
      </div>

      <section className="space-y-4">
        <h2 className="font-mono text-axiom-12 uppercase tracking-[2px] text-[#6B7490]">Create agent</h2>
        <AgentForm
          vaultKeys={vault.data ?? []}
          isSubmitting={createDef.isPending}
          submitError={formErr}
          onSubmit={async (body) => {
            setFormErr(null);
            try {
              await createDef.mutateAsync(body);
              toast.success("Agent created");
            } catch (e) {
              const msg = e instanceof Error ? e.message : "Create failed";
              setFormErr(msg);
              toast.error(msg);
            }
          }}
        />
      </section>

      <section className="space-y-4">
        <h2 className="font-mono text-axiom-12 uppercase tracking-[2px] text-[#6B7490]">Your agents</h2>
        {defs.error ? (
          <p className="text-red-400">{defs.error.message}</p>
        ) : defs.isPending ? (
          <div className="h-24 animate-pulse rounded-lg bg-[#0A0A14]" />
        ) : (
          <AgentList
            projectId={projectId}
            definitions={defs.data ?? []}
            archivingId={archivingId}
            onArchive={async (id) => {
              setArchivingId(id);
              try {
                await archive.mutateAsync(id);
                toast.success("Archived");
              } catch (e) {
                toast.error(e instanceof Error ? e.message : "Archive failed");
              } finally {
                setArchivingId(null);
              }
            }}
          />
        )}
      </section>
    </div>
  );
}
