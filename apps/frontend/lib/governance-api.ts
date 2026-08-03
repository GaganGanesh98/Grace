/**
 * Governance data access for the dashboard.
 *
 * Backend note: there is no GET /v1/governance/receipts list yet. Receipts are discovered via
 * GET /v1/chains (each chain includes receipt summaries) plus GET /v1/governance/receipts/{id} for detail.
 *
 * Auth: session cookie via Next.js BFF routes (`credentials: "include"`). Pass `projectId` from the
 * active project workspace when the user has multiple projects (backend requirement).
 */

import { parseApiError } from "@/lib/api";
import type {
  ActiveGovernancePolicyPayload,
  ApprovalResponsePayload,
  ChainListResponse,
  ExtendHoldResponsePayload,
  GovernanceEngineVerifyResponse,
  GovernanceReceiptRecord,
  PendingReceiptsResponsePayload,
  PendingReceiptSummaryPayload,
} from "@/lib/governance-types";

async function parseJson<T>(res: Response): Promise<T> {
  const body: unknown = await res.json();
  return body as T;
}

/** List workflow chains with embedded receipt summaries (paginated). */
export async function fetchChains(params?: {
  page?: number;
  per_page?: number;
  status?: string;
  projectId?: string;
}): Promise<ChainListResponse> {
  const search = new URLSearchParams();
  if (params?.page != null) {
    search.set("page", String(params.page));
  }
  if (params?.per_page != null) {
    search.set("per_page", String(params.per_page));
  }
  if (params?.status) {
    search.set("status", params.status);
  }
  if (params?.projectId) {
    search.set("project_id", params.projectId);
  }
  const qs = search.toString();
  const res = await fetch(`/api/governance/chains${qs ? `?${qs}` : ""}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<ChainListResponse>(res);
}

/** Active governance YAML policy for the project (from settings; no receipts required). */
export async function fetchActiveGovernancePolicy(projectId: string): Promise<ActiveGovernancePolicyPayload> {
  const qs = new URLSearchParams({ project_id: projectId });
  const res = await fetch(`/api/governance/policies/active?${qs.toString()}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<ActiveGovernancePolicyPayload>(res);
}

/** Full receipt (7-stage payload) for a single governance record. */
export async function fetchReceipt(id: string, shareToken?: string, projectId?: string): Promise<GovernanceReceiptRecord> {
  const qs = new URLSearchParams();
  if (shareToken) {
    qs.set("share_token", shareToken);
  } else if (projectId) {
    qs.set("project_id", projectId);
  }
  const q = qs.toString();
  const res = await fetch(`/api/governance/receipts/${encodeURIComponent(id)}${q ? `?${q}` : ""}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<GovernanceReceiptRecord>(res);
}

export async function verifyReceiptById(receiptId: string, projectId?: string): Promise<GovernanceEngineVerifyResponse> {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await fetch(`/api/governance/verify${qs}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ receipt_id: receiptId }),
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<GovernanceEngineVerifyResponse>(res);
}

/**
 * Flatten all receipt IDs from paged chains, optionally across multiple pages.
 * Use with fetchReceipt for table rows.
 */
export async function collectReceiptIdsFromChains(
  maxPages = 5,
  projectId?: string,
): Promise<{
  chains: ChainListResponse["chains"];
  receiptIds: string[];
}> {
  const chains: ChainListResponse["chains"] = [];
  let page = 1;
  let totalPages = 1;
  const ids = new Set<string>();
  while (page <= totalPages && page <= maxPages) {
    const batch = await fetchChains({ page, per_page: 100, projectId });
    if (page === 1) {
      totalPages = Math.max(1, Math.ceil(batch.total / batch.per_page));
    }
    chains.push(...batch.chains);
    for (const ch of batch.chains) {
      for (const r of ch.records) {
        ids.add(r.receipt_id);
      }
    }
    if (batch.chains.length === 0) {
      break;
    }
    page += 1;
  }
  return { chains, receiptIds: Array.from(ids) };
}

/** Aggregate receipts by fetching each ID (bounded concurrency). */
export async function fetchReceiptsDetailed(
  receiptIds: string[],
  concurrency = 6,
  projectId?: string,
): Promise<Map<string, GovernanceReceiptRecord>> {
  const out = new Map<string, GovernanceReceiptRecord>();
  let next = 0;
  async function worker(): Promise<void> {
    while (true) {
      const idx = next;
      next += 1;
      if (idx >= receiptIds.length) {
        return;
      }
      const id = receiptIds[idx];
      try {
        const rec = await fetchReceipt(id, undefined, projectId);
        out.set(id, rec);
      } catch {
        /* skip missing */
      }
    }
  }
  const n = Math.min(concurrency, Math.max(1, receiptIds.length));
  await Promise.all(Array.from({ length: n }, () => worker()));
  return out;
}

/** Approve a held receipt (JWT via BFF; dashboard session). */
export async function approveReceipt(receiptId: string, reason?: string): Promise<ApprovalResponsePayload> {
  const res = await fetch(
    `/api/governance/receipts/${encodeURIComponent(receiptId)}/approve`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reason ? { reason } : {}),
      cache: "no-store",
    },
  );
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<ApprovalResponsePayload>(res);
}

/** Reject a held receipt (JWT via BFF). */
export async function rejectReceipt(receiptId: string, reason?: string): Promise<ApprovalResponsePayload> {
  const res = await fetch(
    `/api/governance/receipts/${encodeURIComponent(receiptId)}/reject`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reason ? { reason } : {}),
      cache: "no-store",
    },
  );
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<ApprovalResponsePayload>(res);
}

/** Extend the approval window for a held receipt (JWT via BFF). */
export async function extendHold(receiptId: string): Promise<ExtendHoldResponsePayload> {
  const res = await fetch(
    `/api/governance/receipts/${encodeURIComponent(receiptId)}/extend-hold`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      cache: "no-store",
    },
  );
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<ExtendHoldResponsePayload>(res);
}

/** Pending human approvals for the command center (JWT via BFF). */
export async function fetchPendingReceipts(projectId: string): Promise<PendingReceiptSummaryPayload[]> {
  const search = new URLSearchParams({ project_id: projectId });
  const res = await fetch(`/api/governance/receipts/pending?${search.toString()}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  const body = await parseJson<PendingReceiptsResponsePayload>(res);
  return body.receipts;
}

export async function fetchPublicReceipt(id: string, shareToken: string): Promise<GovernanceReceiptRecord> {
  const res = await fetch(
    `/api/public/governance/receipts/${encodeURIComponent(id)}?share_token=${encodeURIComponent(shareToken)}`,
    { cache: "no-store" },
  );
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<GovernanceReceiptRecord>(res);
}
