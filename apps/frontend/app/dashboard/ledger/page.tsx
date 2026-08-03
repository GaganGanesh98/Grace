"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState, type ReactElement } from "react";

import { ChainGroup } from "@/components/chain-group";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { Button } from "@/components/ui/button";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { fetchGovernanceLedgerBundle } from "@/lib/governance-ledger-bundle";
import type { GovernanceChainSummary, GovernanceReceiptRecord } from "@/lib/governance-types";
import { cn } from "@/lib/utils";

type VerdictFilter = "all" | "allow" | "hold" | "deny";
type VerifyFilter = "all" | "pass" | "fail";
type RangeFilter = "24h" | "7d" | "30d" | "custom";

function inRange(iso: string, range: RangeFilter, customFrom?: string, customTo?: string): boolean {
  const t = new Date(iso).getTime();
  if (range === "custom" && customFrom && customTo) {
    const a = new Date(customFrom).getTime();
    const b = new Date(customTo).getTime();
    return t >= a && t <= b + 24 * 60 * 60 * 1000;
  }
  const now = Date.now();
  const ms =
    range === "24h"
      ? 24 * 60 * 60 * 1000
      : range === "7d"
        ? 7 * 24 * 60 * 60 * 1000
        : range === "30d"
          ? 30 * 24 * 60 * 60 * 1000
          : 10 * 365 * 24 * 60 * 60 * 1000;
  return now - t <= ms;
}

export default function LedgerPage(): ReactElement {
  const { activeProjectId } = useProjectWorkspace();
  const ledgerQuery = useQuery({
    queryKey: activeProjectId ? dashboardKeys.ledgerBundle(activeProjectId) : ["axiom", "ledger", "none"],
    queryFn: () => fetchGovernanceLedgerBundle(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });
  const loading = Boolean(activeProjectId) && ledgerQuery.isPending;
  const error =
    ledgerQuery.error instanceof Error
      ? ledgerQuery.error.message
      : ledgerQuery.error
        ? "Failed to load ledger"
        : null;
  const chains = useMemo(
    (): GovernanceChainSummary[] => ledgerQuery.data?.chains ?? [],
    [ledgerQuery.data?.chains],
  );
  const receipts = useMemo(
    (): Map<string, GovernanceReceiptRecord> =>
      ledgerQuery.data?.receipts ?? new Map<string, GovernanceReceiptRecord>(),
    [ledgerQuery.data?.receipts],
  );
  const [verdict, setVerdict] = useState<VerdictFilter>("all");
  const [verify, setVerify] = useState<VerifyFilter>("all");
  const [range, setRange] = useState<RangeFilter>("30d");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const filteredReceipts = useMemo(() => {
    const out = new Map<string, GovernanceReceiptRecord>();
    receipts.forEach((r, id) => {
      const v = r.verdict.verdict;
      if (verdict !== "all" && v !== verdict) {
        return;
      }
      const vs = r.verification?.status ?? "";
      if (verify === "pass" && vs !== "pass") {
        return;
      }
      if (verify === "fail" && vs !== "fail") {
        return;
      }
      const iso = r.intent.created_at;
      if (!inRange(iso, range, customFrom, customTo)) {
        return;
      }
      out.set(id, r);
    });
    return out;
  }, [receipts, verdict, verify, range, customFrom, customTo]);

  const visibleChains = useMemo(() => {
    return chains
      .map((ch) => ({
        ...ch,
        records: ch.records.filter((rec) => filteredReceipts.has(rec.receipt_id)),
      }))
      .filter((ch) => ch.records.length > 0);
  }, [chains, filteredReceipts]);

  const pill = "font-mono text-axiom-12 uppercase tracking-wide";

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-axiom-24 font-medium text-[#F0F2F8]">Governance ledger</h1>
        <p className="mt-2 max-w-3xl text-axiom-15 text-[#A0A8BC]">
          Records are grouped by workflow chain. Only receipts attached to a chain appear here (there is no
          global receipt list API yet).
        </p>
      </header>

      {!activeProjectId ? (
        <div className="rounded-md border border-border-subtle bg-surface-card px-4 py-3 text-axiom-15 text-[#F0F2F8]">
          Select or create a project in the workspace to load the ledger.
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-axiom-15 text-[#F87171]">
          {error}
        </div>
      ) : null}

      <div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
        <div>
          <div className="mb-2 font-mono text-axiom-13 uppercase tracking-wide text-[#A0A8BC]">Verdict</div>
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["all", "All"],
                ["allow", "Authorized"],
                ["hold", "Held"],
                ["deny", "Denied"],
              ] as const
            ).map(([k, lab]) => (
              <Button
                key={k}
                type="button"
                size="sm"
                variant={verdict === k ? "primary" : "secondary"}
                className={cn(
                  pill,
                  verdict === k
                    ? "border-text-primary bg-surface-elevated text-text-primary"
                    : "border-[rgba(255,255,255,0.08)] bg-transparent text-[#A0A8BC]",
                )}
                onClick={() => {
                  setVerdict(k);
                }}
              >
                {lab}
              </Button>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-2 font-mono text-axiom-13 uppercase tracking-wide text-[#A0A8BC]">
            Verification
          </div>
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["all", "All"],
                ["pass", "Compliant"],
                ["fail", "Non-compliant"],
              ] as const
            ).map(([k, lab]) => (
              <Button
                key={k}
                type="button"
                size="sm"
                variant={verify === k ? "primary" : "secondary"}
                className={cn(
                  pill,
                  verify === k
                    ? "border-text-primary bg-surface-elevated text-text-primary"
                    : "border-[rgba(255,255,255,0.08)] bg-transparent text-[#A0A8BC]",
                )}
                onClick={() => {
                  setVerify(k);
                }}
              >
                {lab}
              </Button>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-2 font-mono text-axiom-13 uppercase tracking-wide text-[#A0A8BC]">Date range</div>
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["24h", "Last 24h"],
                ["7d", "7d"],
                ["30d", "30d"],
                ["custom", "Custom"],
              ] as const
            ).map(([k, lab]) => (
              <Button
                key={k}
                type="button"
                size="sm"
                variant={range === k ? "primary" : "secondary"}
                className={cn(
                  pill,
                  range === k
                    ? "border-text-primary bg-surface-elevated text-text-primary"
                    : "border-[rgba(255,255,255,0.08)] bg-transparent text-[#A0A8BC]",
                )}
                onClick={() => {
                  setRange(k);
                }}
              >
                {lab}
              </Button>
            ))}
          </div>
        </div>
        {range === "custom" ? (
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 font-mono text-axiom-12 text-[#A0A8BC]">
              From
              <input
                type="date"
                value={customFrom}
                onChange={(e) => {
                  setCustomFrom(e.target.value);
                }}
                className="rounded border border-[rgba(255,255,255,0.08)] bg-[#0A0A14] px-2 py-1 text-axiom-14 text-[#F0F2F8]"
              />
            </label>
            <label className="flex flex-col gap-1 font-mono text-axiom-12 text-[#A0A8BC]">
              To
              <input
                type="date"
                value={customTo}
                onChange={(e) => {
                  setCustomTo(e.target.value);
                }}
                className="rounded border border-[rgba(255,255,255,0.08)] bg-[#0A0A14] px-2 py-1 text-axiom-14 text-[#F0F2F8]"
              />
            </label>
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="space-y-3">
          <div className="h-12 animate-pulse rounded-lg bg-[#0A0A14]" />
          <div className="h-40 animate-pulse rounded-lg bg-[#0A0A14]" />
        </div>
      ) : null}

      {!loading && activeProjectId && visibleChains.length === 0 ? (
        <p className="text-axiom-15 text-[#6B7490]">No records match the current filters.</p>
      ) : null}

      <div className="space-y-4">
        {visibleChains.map((ch) => (
          <ChainGroup key={ch.id} chain={ch} receipts={filteredReceipts} />
        ))}
      </div>
    </div>
  );
}
