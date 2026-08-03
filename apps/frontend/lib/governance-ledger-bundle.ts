import { collectReceiptIdsFromChains, fetchReceiptsDetailed } from "@/lib/governance-api";
import type { GovernanceChainSummary, GovernanceReceiptRecord } from "@/lib/governance-types";

export type GovernanceLedgerBundle = {
  chains: GovernanceChainSummary[];
  receiptIds: string[];
  receipts: Map<string, GovernanceReceiptRecord>;
};

export async function fetchGovernanceLedgerBundle(
  projectId: string,
  maxChainPages = 5,
): Promise<GovernanceLedgerBundle> {
  const { chains, receiptIds } = await collectReceiptIdsFromChains(maxChainPages, projectId);
  const receipts = await fetchReceiptsDetailed(receiptIds, 8, projectId);
  return { chains, receiptIds, receipts };
}

/** Merge ledger bundles for multiple projects (Receipts page “All projects”). */
export async function fetchGovernanceLedgerBundles(
  projectIds: string[],
  maxChainPages = 5,
): Promise<GovernanceLedgerBundle> {
  const chains: GovernanceChainSummary[] = [];
  const receipts = new Map<string, GovernanceReceiptRecord>();
  const idOrder: string[] = [];
  for (const pid of projectIds) {
    const b = await fetchGovernanceLedgerBundle(pid, maxChainPages);
    chains.push(...b.chains);
    for (const id of b.receiptIds) {
      if (!receipts.has(id)) {
        idOrder.push(id);
      }
    }
    for (const [id, rec] of Array.from(b.receipts.entries())) {
      receipts.set(id, rec);
    }
  }
  return { chains, receiptIds: idOrder, receipts };
}
