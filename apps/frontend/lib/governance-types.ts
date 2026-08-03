/**
 * Types aligned with backend `EngineReceiptResponse`, chain summaries, and verify payloads.
 * @see apps/backend/src/axiom/schemas/governance.py
 */

export type VerdictCode = "allow" | "hold" | "deny" | string;

export type GovernanceIntentPayload = {
  id: string;
  project_id: string;
  agent_id: string;
  action_type: string;
  target: string;
  parameters: Record<string, unknown>;
  risk_declared: string;
  mode: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type GovernanceVerdictPayload = {
  id: string;
  verdict: VerdictCode;
  reason: string | null;
  policy_version: string;
  rules_evaluated: unknown[];
  risk_assessed: string;
  context: Record<string, unknown>;
  created_at: string;
};

export type GovernanceReceiptRecord = {
  id: string;
  intent: GovernanceIntentPayload;
  verdict: GovernanceVerdictPayload;
  execution: Record<string, unknown> | null;
  verification: { status: string; mismatches: unknown[] };
  signatures: {
    ed25519: string;
    ml_dsa_65: string;
    key_id: string;
  };
  merkle: {
    leaf: string;
    root: string;
    depth: number;
    leaf_index?: number | null;
    tree_size?: number | null;
    path: unknown[];
  };
  policy_version: string;
  sealed_at: string | null;
  status: string;
  /** Wall time from intent/receipt created_at to sealed_at; only when status is sealed. */
  duration_ms?: number | null;
  signer_public: { ed25519_public_pem: string; ml_dsa_public_b64: string } | null;
  approval_status?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  approval_reason?: string | null;
  approval_expires_at?: string | null;
};

export type ChainRecordSummary = {
  receipt_id: string;
  intent_id: string;
  verdict_id: string;
  status: string;
  verdict: VerdictCode;
  sealed_at: string | null;
  receipt_hash: string | null;
  created_at: string;
};

export type GovernanceChainSummary = {
  id: string;
  workflow_name: string | null;
  agent_id: string;
  status: string;
  total_actions: number;
  authorized: number;
  held: number;
  denied: number;
  compliant: number;
  non_compliant: number;
  compliance_rate: number;
  chain_signature: { ed25519?: boolean; ml_dsa_65?: boolean } | null;
  started_at: string;
  closed_at: string | null;
  sealed_at: string | null;
  records: ChainRecordSummary[];
};

export type ChainListResponse = {
  chains: GovernanceChainSummary[];
  total: number;
  page: number;
  per_page: number;
};

export type GovernanceEngineVerifyResponse = {
  valid: boolean;
  checks: Record<string, boolean>;
  errors: string[];
};

export type ApprovalResponsePayload = {
  receipt_id: string;
  approval_status: "approved" | "rejected";
  approved_by: string;
  approved_at: string;
  verdict: "allow" | "deny";
  reason: string | null;
};

export type ExtendHoldResponsePayload = {
  approval_expires_at: string;
};

export type PendingReceiptSummaryPayload = {
  receipt_id: string;
  agent_id: string;
  action_type: string;
  target: string;
  risk: string;
  reason: string | null;
  created_at: string;
  approval_expires_at: string;
  time_remaining_seconds: number;
};

export type PendingReceiptsResponsePayload = {
  receipts: PendingReceiptSummaryPayload[];
  total: number;
};

/** GET /v1/governance/policies/active */
export type ActiveGovernancePolicyPayload = {
  name: string;
  display_name: string;
  version: string;
  rules: Array<Record<string, unknown>>;
  is_default_configuration: boolean;
};
