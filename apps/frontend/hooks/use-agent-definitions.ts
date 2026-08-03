"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  archiveAgentDefinition,
  createAgentDefinition,
  fetchAgentDefinition,
  fetchAgentDefinitions,
} from "@/lib/agent-runner-api";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import type { AgentDefinitionOut } from "@/lib/types";

export function useAgentDefinitions(projectId: string | null): ReturnType<
  typeof useQuery<AgentDefinitionOut[], Error>
> {
  return useQuery({
    queryKey: projectId ? dashboardKeys.agentDefinitions(projectId) : ["axiom", "agent-definitions", "none"],
    queryFn: () => fetchAgentDefinitions(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useAgentDefinition(projectId: string | null, definitionId: string | null): ReturnType<
  typeof useQuery<AgentDefinitionOut, Error>
> {
  return useQuery({
    queryKey:
      projectId && definitionId
        ? dashboardKeys.agentDefinition(projectId, definitionId)
        : ["axiom", "agent-definition", "none"],
    queryFn: () => fetchAgentDefinition(projectId!, definitionId!),
    enabled: Boolean(projectId && definitionId),
  });
}

export function useCreateAgentDefinition(projectId: string): ReturnType<
  typeof useMutation<AgentDefinitionOut, Error, Record<string, unknown>>
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => createAgentDefinition(projectId, body),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: dashboardKeys.agentDefinitions(projectId) });
      await qc.invalidateQueries({
        queryKey: dashboardKeys.agentDefinitionsNonArchivedCount(projectId),
      });
    },
  });
}

export function useArchiveAgentDefinition(projectId: string): ReturnType<
  typeof useMutation<AgentDefinitionOut, Error, string>
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (definitionId: string) => archiveAgentDefinition(projectId, definitionId),
    onSuccess: async (_data, definitionId) => {
      await qc.invalidateQueries({ queryKey: dashboardKeys.agentDefinitions(projectId) });
      await qc.invalidateQueries({
        queryKey: dashboardKeys.agentDefinitionsNonArchivedCount(projectId),
      });
      await qc.invalidateQueries({
        queryKey: dashboardKeys.agentDefinition(projectId, definitionId),
      });
    },
  });
}
