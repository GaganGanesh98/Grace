/** Stable React Query keys for dashboard / governance data. */

export const dashboardKeys = {
  projects: ["axiom", "projects"] as const,
  projectKeys: (projectId: string) => ["axiom", "project-keys", projectId] as const,
  ledgerBundle: (projectId: string) => ["axiom", "governance-ledger-bundle", projectId] as const,
  /** Alias: Phase 7.6 invalidation map (same data as `ledgerBundle`, incl. activity table / receipts). */
  governanceLedgerBundle: (projectId: string) => ["axiom", "governance-ledger-bundle", projectId] as const,
  /** Alias of `ledgerBundle` — activity table data source. */
  receiptsDetailed: (projectId: string) => ["axiom", "governance-ledger-bundle", projectId] as const,
  pendingReceipts: (projectId: string) => ["axiom", "governance-pending", projectId] as const,
  /** Alias: pending approval queue (Phase 7.6 invalidation map). */
  pendingApprovals: (projectId: string) => ["axiom", "governance-pending", projectId] as const,
  /** Same query as pending receipts — attention strip is derived from that list. */
  attentionStrip: (projectId: string) => ["axiom", "governance-pending", projectId] as const,
  /** Active governance YAML policy (backend / project settings). */
  activePolicy: (projectId: string) => ["axiom", "governance-active-policy", projectId] as const,
  receipt: (receiptId: string, projectId: string) =>
    ["axiom", "governance-receipt", projectId, receiptId] as const,
  vaultKeys: (projectId: string) => ["axiom", "vault-keys", projectId] as const,
  agentDefinitions: (projectId: string) => ["axiom", "agent-definitions", projectId] as const,
  /** Total non-archived rows; matches `meta.total` from GET /agent-definitions (paged). */
  agentDefinitionsNonArchivedCount: (projectId: string) =>
    ["axiom", "agent-definitions-count", projectId] as const,
  agentDefinition: (projectId: string, definitionId: string) =>
    ["axiom", "agent-definition", projectId, definitionId] as const,
  agentRuns: (projectId: string) => ["axiom", "agent-runs", projectId] as const,
  agentRun: (projectId: string, runId: string) => ["axiom", "agent-run", projectId, runId] as const,
  commandCenterPosture: (projectId: string, window: string) =>
    ["axiom", "command-center", "posture", projectId, window] as const,
  commandCenterCryptoHealth: (projectId: string) =>
    ["axiom", "command-center", "crypto-health", projectId] as const,
  commandCenterPolicyBreakdown: (projectId: string, window: string) =>
    ["axiom", "command-center", "policy-breakdown", projectId, window] as const,
  commandCenterTsa: (projectId: string) => ["axiom", "command-center", "tsa-status", projectId] as const,
  commandCenterTsaStatus: (projectId: string) => ["axiom", "command-center", "tsa-status", projectId] as const,
  /** Full agent definitions list for Command Center name resolution (batched, all pages). */
  commandCenterAgentDefinitionsAll: (projectId: string) =>
    ["axiom", "command-center", "agent-definitions-all", projectId] as const,
  /** GET /api/projects/:id (project metadata for workspace header and settings). */
  project: (projectId: string) => ["axiom", "project", projectId] as const,
  projectHeader: (projectId: string) => ["axiom", "project-header", projectId] as const,
  projectMetrics: (projectId: string) => ["axiom", "project-metrics", projectId] as const,
  projectMembers: (projectId: string) => ["axiom", "project-members", projectId] as const,
  projectPolicies: (projectId: string) => ["axiom", "project-policies", projectId] as const,
  /** Paged + filtered list (Runs tab + filters); not an alias of `agentRuns` when filter differs. */
  projectRunsList: (projectId: string, filterKey: string) =>
    ["axiom", "project-runs-list", projectId, filterKey] as const,
  /** Partial key: invalidates all `projectRunsList` for this project. */
  projectRunsListAll: (projectId: string) => ["axiom", "project-runs-list", projectId] as const,
  recentProjectRuns: (projectId: string) => ["axiom", "recent-project-runs", projectId] as const,
};
