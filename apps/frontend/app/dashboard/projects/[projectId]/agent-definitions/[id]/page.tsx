"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAgentDefinition } from "@/hooks/use-agent-definitions";
import { useCreateAgentRun } from "@/hooks/use-agent-runs";

export default function AgentDefinitionDetailPage(): ReactElement {
  const params = useParams<{ projectId: string; id: string }>();
  const router = useRouter();
  const projectId = params.projectId;
  const defId = params.id;
  const q = useAgentDefinition(projectId, defId);
  const createRun = useCreateAgentRun(projectId);
  const [goal, setGoal] = useState("");
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}/agent-definitions`}
        className="font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-electric)] hover:underline"
      >
        ← Agents
      </Link>

      {q.isPending ? (
        <div className="h-32 animate-pulse rounded-lg bg-[#0A0A14]" />
      ) : q.error ? (
        <p className="text-red-400">{q.error.message}</p>
      ) : !q.data ? (
        <p className="text-[#6B7490]">Not found.</p>
      ) : (
        <>
          <div>
            <p className="font-mono text-axiom-11 uppercase text-[#6B7490]">Agent</p>
            <h1 className="mt-2 font-mono text-axiom-24 font-medium text-[#F0F2F8]">{q.data.name}</h1>
            <p className="mt-2 font-mono text-axiom-14 text-[#A0A8BC]">{q.data.model}</p>
            {q.data.is_archived ? (
              <p className="mt-2 font-mono text-axiom-13 uppercase text-amber-400">Archived — run disabled</p>
            ) : null}
          </div>

          {!q.data.is_archived ? (
            <div className="flex flex-wrap gap-3">
              <Button
                type="button"
                className="bg-neutral-100 text-text-inverse hover:bg-white"
                onClick={() => {
                  setOpen(true);
                }}
              >
                Run
              </Button>
            </div>
          ) : null}
        </>
      )}

      {open ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="run-goal-title"
        >
          <div className="w-full max-w-lg rounded-lg border border-border-subtle bg-[#080810] p-6">
            <h2 id="run-goal-title" className="font-mono text-axiom-14 uppercase tracking-wide text-[#F0F2F8]">
              Run goal
            </h2>
            <div className="mt-4">
              <Label className="font-mono text-axiom-11 uppercase text-[#6B7490]">Goal</Label>
              <Input
                value={goal}
                onChange={(e) => {
                  setGoal(e.target.value);
                }}
                className="mt-2 border-[rgba(255,255,255,0.1)] bg-[#0A0A14]"
                placeholder="What should the agent do?"
              />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setOpen(false);
                }}
              >
                Cancel
              </Button>
              <Button
                type="button"
                data-testid="start-agent-run"
                className="bg-neutral-100 text-text-inverse hover:bg-white"
                disabled={createRun.isPending || !goal.trim()}
                onClick={() => {
                  createRun.mutate(
                    { agent_definition_id: defId, input: { goal: goal.trim() } },
                    {
                      onSuccess: ({ run, wsToken }) => {
                        try {
                          sessionStorage.setItem(`axiom:ws:${run.id}`, wsToken);
                        } catch {
                          /* ignore */
                        }
                        setOpen(false);
                        router.push(`/dashboard/projects/${projectId}/runs/${run.id}`);
                      },
                      onError: (e) => {
                        toast.error(e instanceof Error ? e.message : "Run failed");
                      },
                    },
                  );
                }}
              >
                Start run
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
