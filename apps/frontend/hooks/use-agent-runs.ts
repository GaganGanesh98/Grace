"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelAgentRun,
  createAgentRun,
  fetchAgentRun,
  fetchAgentRuns,
  mintAgentRunWsToken,
} from "@/lib/agent-runner-api";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import type { AgentRunOut } from "@/lib/types";

export function useAgentRuns(projectId: string | null): ReturnType<typeof useQuery<AgentRunOut[], Error>> {
  return useQuery({
    queryKey: projectId ? dashboardKeys.agentRuns(projectId) : ["axiom", "agent-runs", "none"],
    queryFn: () => fetchAgentRuns(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useAgentRun(projectId: string | null, runId: string | null): ReturnType<
  typeof useQuery<AgentRunOut, Error>
> {
  return useQuery({
    queryKey:
      projectId && runId ? dashboardKeys.agentRun(projectId, runId) : ["axiom", "agent-run", "none"],
    queryFn: () => fetchAgentRun(projectId!, runId!),
    enabled: Boolean(projectId && runId),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "pending" || s === "running" ? 2000 : false;
    },
  });
}

export function useCreateAgentRun(projectId: string): ReturnType<
  typeof useMutation<
    { run: AgentRunOut; wsToken: string },
    Error,
    { agent_definition_id: string; input: Record<string, unknown> }
  >
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body) => {
      const run = await createAgentRun(projectId, body);
      const { token } = await mintAgentRunWsToken(projectId, run.id);
      return { run, wsToken: token };
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: dashboardKeys.agentRuns(projectId) });
      await qc.invalidateQueries({ queryKey: dashboardKeys.recentProjectRuns(projectId) });
      await qc.invalidateQueries({ queryKey: dashboardKeys.projectMetrics(projectId) });
    },
  });
}

export function useCancelAgentRun(projectId: string): ReturnType<
  typeof useMutation<AgentRunOut, Error, string>
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => cancelAgentRun(projectId, runId),
    onSuccess: async (_data, runId) => {
      await qc.invalidateQueries({ queryKey: dashboardKeys.agentRuns(projectId) });
      await qc.invalidateQueries({ queryKey: dashboardKeys.agentRun(projectId, runId) });
    },
  });
}
