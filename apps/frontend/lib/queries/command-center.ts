import { useQuery } from "@tanstack/react-query";

import {
  fetchCommandCenterCryptoHealth,
  fetchCommandCenterPolicyBreakdown,
  fetchCommandCenterPosture,
  fetchCommandCenterTsaStatusOrThrow,
} from "@/lib/command-center-api";
import type { CryptoHealthOut, PolicyBreakdownOut, PostureMetrics, TsaStatusOut } from "@/lib/command-center-types";
import { dashboardKeys } from "@/lib/dashboard-query-keys";

const STALE = 0;

type ProjectArgs = { projectId: string | null };

export function usePostureQuery({ projectId, window = "24h" }: ProjectArgs & { window?: string }) {
  return useQuery<PostureMetrics, Error>({
    queryKey: projectId ? dashboardKeys.commandCenterPosture(projectId, window) : ["axiom", "cc-posture", "none"],
    queryFn: () => fetchCommandCenterPosture(projectId!, window),
    enabled: Boolean(projectId),
    staleTime: STALE,
  });
}

export function useCryptoHealthQuery({ projectId }: ProjectArgs) {
  return useQuery<CryptoHealthOut, Error>({
    queryKey: projectId ? dashboardKeys.commandCenterCryptoHealth(projectId) : ["axiom", "cc-crypto", "none"],
    queryFn: () => fetchCommandCenterCryptoHealth(projectId!),
    enabled: Boolean(projectId),
    staleTime: STALE,
  });
}

/**
 * Policy stats; on failure returns `null` (graceful degradation) so the card keeps the policy name from the active-policy query.
 */
export function usePolicyBreakdownQuery({ projectId, window = "24h" }: ProjectArgs & { window?: string }) {
  return useQuery<PolicyBreakdownOut | null, Error>({
    queryKey: projectId
      ? dashboardKeys.commandCenterPolicyBreakdown(projectId, window)
      : ["axiom", "cc-policy-br", "none"],
    queryFn: async () => {
      try {
        return await fetchCommandCenterPolicyBreakdown(projectId!, window);
      } catch {
        /* 401: redirect to login in fetch; still degrade stats to "—" per Phase 7.5.3 Clause 3. */
        return null;
      }
    },
    enabled: Boolean(projectId),
    staleTime: STALE,
  });
}

export type TsaStatusResult = { kind: "ok"; data: TsaStatusOut } | { kind: "fallback" };

/**
 * TSA line for the crypto footer. On any failure (including 401; redirect in fetch) returns `fallback` so the footer never shows an error state (Clause 4).
 */
export function useTsaStatusQuery({ projectId }: ProjectArgs) {
  return useQuery<TsaStatusResult, Error>({
    queryKey: projectId ? dashboardKeys.commandCenterTsa(projectId) : ["axiom", "cc-tsa", "none"],
    queryFn: async () => {
      try {
        const data = await fetchCommandCenterTsaStatusOrThrow(projectId!);
        return { kind: "ok" as const, data };
      } catch {
        return { kind: "fallback" as const };
      }
    },
    enabled: Boolean(projectId),
    staleTime: STALE,
  });
}
