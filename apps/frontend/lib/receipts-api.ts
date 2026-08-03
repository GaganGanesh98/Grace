/**
 * Receipt list/detail/verify helpers for the Receipts dashboard page.
 * Listing uses GET /v1/chains + GET /v1/governance/receipts/{id} (no dedicated list route).
 */

import { verifyReceiptById, fetchReceipt } from "@/lib/governance-api";
import { fetchGovernanceLedgerBundle, fetchGovernanceLedgerBundles } from "@/lib/governance-ledger-bundle";
import type { GovernanceReceiptRecord } from "@/lib/governance-types";
import { toUiVerdict } from "@/lib/governance-display";
import type { UiVerdict } from "@/lib/governance-display";

export type ReceiptVerdict = UiVerdict;

export type ReceiptStatus = "pending" | "sealed" | "verified" | "failed" | string;

export interface ReceiptListItem {
  id: string;
  project_id: string;
  status: ReceiptStatus;
  verdict: ReceiptVerdict;
  action_type: string;
  upstream_provider: string;
  upstream_model: string;
  upstream_status: number;
  total_tokens: number | null;
  sealed_at: string | null;
  created_at: string;
  upstream_latency_ms: number;
}

export interface ReceiptDetail extends ReceiptListItem {
  receipt_hash_hex: string;
  ed25519_sig_hex: string;
  ml_dsa_sig_hex: string;
  merkle_leaf_hex: string;
  merkle_root_hex: string | null;
  merkle_proof: unknown;
  key_id: string;

  target: string;
  http_status: number;
  upstream_latency_ms: number;
  request_hash_hex: string;
  response_hash_hex: string;
  vault_key_id: string;

  approval_status: string | null;
  approved_by_user_id: string | null;
  approved_by_email: string | null;
  approved_at: string | null;
  approval_reason: string | null;

  intent_created_at: string;
  executed_at_label: string | null;
  token_usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null;
}

function base64ToHex(b64: string): string {
  if (!b64) {
    return "";
  }
  try {
    const bin = atob(b64);
    let hex = "";
    for (let i = 0; i < bin.length; i++) {
      hex += bin.charCodeAt(i).toString(16).padStart(2, "0");
    }
    return hex;
  } catch {
    return "";
  }
}

function readExecutionFields(execution: Record<string, unknown> | null): {
  upstream_provider: string;
  upstream_model: string;
  upstream_status: number;
  upstream_latency_ms: number;
  total_tokens: number | null;
  request_hash_hex: string;
  response_hash_hex: string;
  vault_key_id: string;
  target: string;
  http_status: number;
  token_usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null;
} {
  const ex = execution ?? {};
  const auditRaw = ex.upstream_audit;
  const audit =
    auditRaw && typeof auditRaw === "object" ? (auditRaw as Record<string, unknown>) : ({} as Record<string, unknown>);

  const tu = audit.token_usage;
  const tokenUsage =
    tu && typeof tu === "object"
      ? (tu as { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number })
      : null;
  const totalTokens =
    tokenUsage && typeof tokenUsage.total_tokens === "number" ? tokenUsage.total_tokens : null;

  const httpFromEx = ex.http_status;
  const httpFromAudit = audit.upstream_status;
  const httpStatus =
    typeof httpFromEx === "number"
      ? httpFromEx
      : typeof httpFromAudit === "number"
        ? httpFromAudit
        : 0;

  const latRaw = audit.upstream_latency_ms;
  const latency = typeof latRaw === "number" ? latRaw : 0;

  const targetStr = typeof ex.target === "string" ? ex.target : "";

  return {
    upstream_provider: typeof audit.upstream_provider === "string" ? audit.upstream_provider : "",
    upstream_model: typeof audit.upstream_model === "string" ? audit.upstream_model : "",
    upstream_status: typeof httpFromAudit === "number" ? httpFromAudit : httpStatus,
    upstream_latency_ms: latency,
    total_tokens: totalTokens,
    request_hash_hex: typeof audit.request_hash === "string" ? audit.request_hash : "",
    response_hash_hex: typeof audit.response_hash === "string" ? audit.response_hash : "",
    vault_key_id: typeof audit.vault_key_id === "string" ? audit.vault_key_id : "",
    target: targetStr,
    http_status: httpStatus,
    token_usage: tokenUsage,
  };
}

export function governanceRecordToListItem(r: GovernanceReceiptRecord): ReceiptListItem {
  const xf = readExecutionFields(r.execution);
  const actionType = r.intent.action_type || (typeof r.execution?.action_type === "string" ? r.execution.action_type : "") || "—";

  return {
    id: r.id,
    project_id: r.intent.project_id,
    status: r.status,
    verdict: toUiVerdict(r.verdict.verdict),
    action_type: actionType,
    upstream_provider: xf.upstream_provider,
    upstream_model: xf.upstream_model,
    upstream_status: xf.upstream_status,
    total_tokens: xf.total_tokens,
    sealed_at: r.sealed_at,
    created_at: r.intent.created_at,
    upstream_latency_ms: xf.upstream_latency_ms,
  };
}

export function governanceRecordToDetail(r: GovernanceReceiptRecord): ReceiptDetail {
  const base = governanceRecordToListItem(r);
  const xf = readExecutionFields(r.execution);
  const leafHex = r.merkle.leaf || "";
  const edHex = base64ToHex(r.signatures.ed25519);
  const mlHex = base64ToHex(r.signatures.ml_dsa_65);

  const ex = r.execution;
  const executedAtRaw = ex && typeof ex.executed_at === "string" ? ex.executed_at : null;

  return {
    ...base,
    target: xf.target || r.intent.target || "—",
    http_status: xf.http_status,
    upstream_latency_ms: xf.upstream_latency_ms,
    request_hash_hex: xf.request_hash_hex,
    response_hash_hex: xf.response_hash_hex,
    vault_key_id: xf.vault_key_id,
    receipt_hash_hex: leafHex,
    ed25519_sig_hex: edHex,
    ml_dsa_sig_hex: mlHex,
    merkle_leaf_hex: leafHex,
    merkle_root_hex: r.merkle.root || null,
    merkle_proof: r.merkle.path,
    key_id: r.signatures.key_id || "—",
    approval_status: r.approval_status ?? null,
    approved_by_user_id: null,
    approved_by_email: r.approved_by ?? null,
    approved_at: r.approved_at ?? null,
    approval_reason: r.approval_reason ?? null,
    intent_created_at: r.intent.created_at,
    executed_at_label: executedAtRaw,
    token_usage: xf.token_usage,
  };
}

export async function listReceipts(params: {
  project_id?: string;
  /** When set (e.g. all workspace projects), merges chain-derived receipts. */
  project_ids?: string[];
  verdict?: ReceiptVerdict;
  limit?: number;
  offset?: number;
}): Promise<{ items: ReceiptListItem[]; total: number }> {
  const ids = params.project_ids?.length
    ? params.project_ids
    : params.project_id
      ? [params.project_id]
      : [];

  if (ids.length === 0) {
    return { items: [], total: 0 };
  }

  const bundle =
    ids.length === 1
      ? await fetchGovernanceLedgerBundle(ids[0]!)
      : await fetchGovernanceLedgerBundles(ids);

  let items = Array.from(bundle.receipts.values()).map(governanceRecordToListItem);

  if (params.verdict) {
    items = items.filter((i) => i.verdict === params.verdict);
  }

  items.sort((a, b) => {
    const ta = new Date(a.created_at).getTime();
    const tb = new Date(b.created_at).getTime();
    return tb - ta;
  });

  const total = items.length;
  const limit = params.limit ?? total;
  const offset = params.offset ?? 0;
  const page = items.slice(offset, offset + limit);

  return { items: page, total };
}

export async function getReceipt(receiptId: string, projectId?: string): Promise<ReceiptDetail> {
  const r = await fetchReceipt(receiptId, undefined, projectId);
  return governanceRecordToDetail(r);
}

export async function verifyReceipt(receiptId: string, projectId?: string): Promise<{
  valid: boolean;
  ed25519_valid: boolean;
  ml_dsa_valid: boolean;
  merkle_valid: boolean;
  errors: string[];
}> {
  const res = await verifyReceiptById(receiptId, projectId);
  const checks = res.checks && typeof res.checks === "object" ? (res.checks as Record<string, boolean>) : {};
  return {
    valid: res.valid,
    ed25519_valid: Boolean(checks.ed25519),
    ml_dsa_valid: Boolean(checks.ml_dsa_65),
    merkle_valid: Boolean(checks.merkle),
    errors: Array.isArray(res.errors) ? res.errors : [],
  };
}
