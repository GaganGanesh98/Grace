"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { fetchAllAgentDefinitions } from "@/lib/agent-runner-api";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { useProjectIdFromLayout } from "@/lib/projects/project-id-context";
import { API_MAX_PER_PAGE, fetchAgentRunsForProject } from "@/lib/projects/project-workspace-api";
import type { AgentRunOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCreateAgentRun } from "@/hooks/use-agent-runs";

/* ─── Constants ─── */
const ITER_STEPS = [5, 10, 20, 50] as const;

/* ─── Overview ─── */
export function OverviewTabPanel(): ReactElement {
  const projectId = useProjectIdFromLayout();
  const searchParams = useSearchParams();
  const preAgent = searchParams.get("preselectAgent");
  const qc = useQueryClient();
  const router = useRouter();

  const agentsQ = useQuery({
    queryKey: dashboardKeys.agentDefinitions(projectId),
    queryFn: () => fetchAllAgentDefinitions(projectId),
  });

  const recentQ = useQuery({
    queryKey: dashboardKeys.recentProjectRuns(projectId),
    queryFn: () => fetchAgentRunsForProject(projectId, { page: 1, perPage: 4 }),
    select: (e) => e.data,
  });

  const metricsQ = useQuery({
    queryKey: dashboardKeys.projectMetrics(projectId),
    queryFn: () => fetchAgentRunsForProject(projectId, { page: 1, perPage: API_MAX_PER_PAGE }),
  });

  const [agentId, setAgentId] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [goalErr, setGoalErr] = useState<string | null>(null);
  const [iterI, setIterI] = useState(1);
  const [dry, setDry] = useState(false);
  const create = useCreateAgentRun(projectId);

  useEffect(() => {
    const list = agentsQ.data;
    if (!list?.length) {
      return;
    }
    if (preAgent && list.some((a) => a.id === preAgent)) {
      setAgentId(preAgent);
      return;
    }
    if (!agentId) {
      setAgentId(list[0]?.id ?? null);
    }
  }, [agentsQ.data, preAgent, agentId]);

  const agents = useMemo(() => agentsQ.data ?? [], [agentsQ.data]);
  const disabled = agents.length === 0;
  const nameByDef = useMemo(() => {
    const m = new Map<string, string>();
    for (const a of agents) {
      m.set(a.id, a.name);
    }
    return m;
  }, [agents]);

  const onRun = useCallback((): void => {
    if (!goal.trim()) {
      setGoalErr("Goal is required.");
      return;
    }
    if (!agentId) {
      return;
    }
    setGoalErr(null);
    const maxIter = ITER_STEPS[iterI] ?? 10;
    create.mutate(
      {
        agent_definition_id: agentId,
        input: { goal: goal.trim(), max_iter: maxIter, dry_run: dry },
      },
      {
        onSuccess: (out) => {
          setGoal("");
          toast.success("RUN STARTED", {
            description: (
              <span className="font-mono">
                Run{" "}
                <Link
                  className="text-[var(--axiom-electric)] underline"
                  href={`/dashboard/ledger/${out.run.id}`}
                >
                  {out.run.id}
                </Link>
              </span>
            ),
            duration: 5000,
          });
          void qc.invalidateQueries({ queryKey: dashboardKeys.recentProjectRuns(projectId) });
        },
        onError: (e) => {
          toast.error("RUN FAILED TO START", { description: e instanceof Error ? e.message : "Error" });
        },
      },
    );
  }, [agentId, create, goal, iterI, dry, projectId, qc]);

  const metrics = useProjectMetrics30d(metricsQ.data?.data);
  return (
    <div className="space-y-8">
      <section
        className={cn("rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] p-6", disabled && "pointer-events-none opacity-50")}
      >
        <h2 className="font-mono text-axiom-12 uppercase tracking-[1.5px] text-[var(--axiom-text)]">
          Run an agent
        </h2>
        {disabled ? (
          <div className="mt-4 text-center">
            <p className="font-mono text-axiom-13 text-[var(--axiom-text-muted)]">
              No agents yet. Create one to run.
            </p>
            <Button
              type="button"
              className="mt-4"
              onClick={() => {
                router.push(`${`/dashboard/projects/${projectId}/agents`}?new=1`);
              }}
            >
              + New agent
            </Button>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <div>
              <p className="font-mono text-axiom-10 uppercase text-[var(--axiom-text-label)]">
                1. Select agent
              </p>
              <select
                className="mt-1 w-full max-w-[320px] rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg)] px-3 py-2 font-mono text-axiom-13 text-[var(--axiom-text)]"
                value={agentId ?? ""}
                onChange={(e) => {
                  setAgentId(e.target.value);
                }}
              >
                {agents
                  .filter((a) => !a.is_archived)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} — {a.model}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <p className="font-mono text-axiom-10 uppercase text-[var(--axiom-text-label)]">2. Goal</p>
              <textarea
                className="mt-1 w-full min-h-[80px] resize-y rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg)] p-3 font-mono text-axiom-13"
                placeholder="Describe what you want the agent to accomplish..."
                value={goal}
                onChange={(e) => {
                  setGoal(e.target.value);
                  setGoalErr(null);
                }}
              />
              {goalErr ? <p className="mt-1 text-axiom-12 text-red-400">{goalErr}</p> : null}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-4">
                <button
                  type="button"
                  className="font-mono text-axiom-12 text-[var(--axiom-text-muted)]"
                  onClick={() => {
                    setIterI((i) => (i + 1) % ITER_STEPS.length);
                  }}
                >
                  max iter: {ITER_STEPS[iterI]}
                </button>
                <label className="flex items-center gap-2 font-mono text-axiom-12 text-[var(--axiom-text-muted)]">
                  <input type="checkbox" checked={dry} onChange={(e) => setDry(e.target.checked)} />
                  dry run
                </label>
              </div>
              <button
                type="button"
                onClick={onRun}
                disabled={create.isPending}
                className="bg-[var(--axiom-electric)] px-5 py-2 font-mono text-axiom-12 font-medium uppercase text-black"
              >
                Run agent
              </button>
            </div>
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-mono text-axiom-12 uppercase tracking-wider text-[var(--axiom-text)]">
            Recent runs
          </h2>
          <Link
            href={`/dashboard/projects/${projectId}/runs`}
            className="font-mono text-axiom-12 text-[var(--axiom-electric)]"
          >
            View all →
          </Link>
        </div>
        <RecentRunsTable
          runs={recentQ.data ?? []}
          agentName={(id) => nameByDef.get(id) ?? "—"}
        />
      </section>

      <section>
        <h2 className="mb-3 font-mono text-axiom-12 uppercase tracking-wider text-[var(--axiom-text)]">
          Project metrics
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <MetricCard
            title="Total runs (30d)"
            value={metrics.totalStr}
            sub={metrics.pct}
            subTone="ok"
          />
          <MetricCard title="Cost (MTD)" value={metrics.cost} sub="your LLM provider bills" subTone="muted" />
          <MetricCard
            title="Governance blocks"
            value={metrics.gov}
            sub={metrics.govSub}
            subTone={metrics.govTone}
          />
        </div>
      </section>
    </div>
  );
}

function useProjectMetrics30d(
  runs: AgentRunOut[] | undefined,
): {
  totalStr: string;
  pct: string;
  cost: string;
  gov: string;
  govSub: string;
  govTone: "muted" | "danger" | "ok";
} {
  return useMemo(() => {
    if (!runs || runs.length === 0) {
      return {
        totalStr: "—",
        pct: "—",
        cost: "—",
        gov: "—",
        govSub: "no data for governance this period",
        govTone: "muted" as const,
      };
    }
    const now = Date.now();
    const d30 = now - 30 * 24 * 60 * 60 * 1000;
    const in30 = runs.filter((r) => new Date(r.created_at).getTime() >= d30);
    const ok = in30.filter((r) => r.status === "succeeded").length;
    const tot = in30.length;
    const pct = tot === 0 ? "—" : `${Math.round((ok / tot) * 100)}% success`;
    return {
      totalStr: String(tot),
      pct,
      cost: "—",
      gov: "—",
      govSub: "governance denials are not yet attributed per run in the API",
      govTone: "muted" as const,
    };
  }, [runs]);
}

function MetricCard({
  title,
  value,
  sub,
  subTone,
}: {
  title: string;
  value: string;
  sub: string;
  subTone: "ok" | "muted" | "danger";
}): ReactElement {
  return (
    <div className="rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg-alt)] p-4">
      <p className="font-mono text-axiom-10 uppercase text-[var(--axiom-text-label)]">{title}</p>
      <p className="mt-2 font-mono text-axiom-22 text-[var(--axiom-text)]">{value}</p>
      <p
        className={cn(
          "mt-1 font-mono text-axiom-12",
          subTone === "ok" && "text-[var(--axiom-success)]",
          subTone === "muted" && "text-[var(--axiom-text-dim)]",
          subTone === "danger" && "text-red-400",
        )}
      >
        {sub}
      </p>
    </div>
  );
}

function statusChip(s: string): { cls: string; label: string } {
  if (s === "succeeded") {
    return { cls: "bg-[var(--axiom-success)]/20 text-[var(--axiom-success)]", label: "COMPLETED" };
  }
  if (s === "failed") {
    return { cls: "bg-red-500/20 text-red-400", label: "FAILED" };
  }
  if (s === "running") {
    return { cls: "bg-blue-500/20 text-blue-300", label: "RUNNING" };
  }
  if (s === "pending") {
    return { cls: "bg-[var(--axiom-warn)]/20 text-[var(--axiom-warn)]", label: "PENDING" };
  }
  return { cls: "bg-[var(--axiom-warn)]/20 text-[var(--axiom-warn)]", label: s.toUpperCase() };
}

function RecentRunsTable({ runs, agentName }: { runs: AgentRunOut[]; agentName: (id: string) => string }): ReactElement {
  if (runs.length === 0) {
    return <p className="p-4 font-mono text-axiom-13 text-[var(--axiom-text-dim)]">No runs yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[700px] border-collapse font-mono text-axiom-12">
        <thead>
          <tr className="border-b border-[var(--axiom-border)] text-left text-axiom-10 uppercase text-[var(--axiom-text-label)]">
            <th className="w-[140px] py-2 pr-2">Agent</th>
            <th className="min-w-0 py-2 pr-2">Goal</th>
            <th className="w-[80px] py-2 pr-2">Time</th>
            <th className="w-[120px] py-2 pr-2">Status</th>
            <th className="w-[100px] py-2 pr-2">Cost</th>
            <th className="w-[80px] py-2" />
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const g = (r.input_payload?.goal as string | undefined) ?? "—";
            const ch = statusChip(r.status);
            return (
              <tr
                key={r.id}
                className="group cursor-pointer border-b border-[var(--axiom-border)]/50 transition hover:border-l-2 hover:border-l-[var(--axiom-electric)] hover:bg-[var(--axiom-electric)]/5"
                onClick={() => {
                  window.location.assign(`/dashboard/ledger/${r.id}`);
                }}
              >
                <td className="py-2 pr-2 align-top text-[var(--axiom-text)]">
                  {agentName(r.agent_definition_id)}
                </td>
                <td className="max-w-[1px] truncate py-2 pr-2 text-[var(--axiom-text-muted)]">{g}</td>
                <td className="whitespace-nowrap py-2 pr-2 text-[var(--axiom-text-dim)]">
                  {r.started_at
                    ? new Date(r.started_at).toLocaleTimeString()
                    : new Date(r.created_at).toLocaleTimeString()}
                </td>
                <td className="py-2 pr-2">
                  <span className={cn("rounded px-1.5 py-0.5 text-axiom-10", ch.cls)}>{ch.label}</span>
                </td>
                <td className="py-2 pr-2">—</td>
                <td className="py-2 text-right text-[var(--axiom-text-dim)] opacity-0 group-hover:opacity-100">
                  Replay
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
