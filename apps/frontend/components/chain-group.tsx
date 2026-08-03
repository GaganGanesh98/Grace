"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState, type ReactElement } from "react";

import { VerdictBadge } from "@/components/verdict-badge";
import { VerificationBadge } from "@/components/verification-badge";
import {
  formatRecordId,
  toUiVerdict,
  toUiVerification,
  truncateMiddle,
  type UiVerdict,
} from "@/lib/governance-display";
import type { GovernanceChainSummary, GovernanceReceiptRecord } from "@/lib/governance-types";

type RowModel = {
  receiptId: string;
  time: string;
  agent: string;
  action: string;
  target: string;
  verdict: UiVerdict;
  verification: "COMPLIANT" | "NON-COMPLIANT" | "PENDING";
};

function formatRowTime(iso: string): string {
  if (!iso) {
    return "—";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function ChainGroup({
  chain,
  receipts,
}: {
  chain: GovernanceChainSummary;
  receipts: Map<string, GovernanceReceiptRecord>;
}): ReactElement {
  const [open, setOpen] = useState(true);
  const label = chain.workflow_name?.trim() || `Chain ${formatRecordId(chain.id)}`;
  const Icon = open ? ChevronDown : ChevronRight;

  const rows: RowModel[] = chain.records.map((r) => {
    const full = receipts.get(r.receipt_id);
    const intent = full?.intent;
    const timeIso = intent?.created_at ?? r.created_at;
    return {
      receiptId: r.receipt_id,
      time: formatRowTime(timeIso),
      agent: intent?.agent_id ?? chain.agent_id,
      action: intent?.action_type ?? "—",
      target: truncateMiddle(intent?.target ?? "—", 40),
      verdict: toUiVerdict(full?.verdict.verdict ?? r.verdict),
      verification: full
        ? toUiVerification(full.verification?.status ?? "", full.status === "sealed")
        : "PENDING",
    };
  });

  return (
    <div className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0A0A14]">
      <button
        type="button"
        className="flex w-full items-center gap-2 border-b border-border-subtle px-4 py-3 text-left transition hover:bg-[rgba(255,255,255,0.02)]"
        onClick={() => {
          setOpen(!open);
        }}
      >
        <Icon className="h-4 w-4 shrink-0 text-[var(--axiom-electric)]" />
        <span className="font-[family-name:var(--font-sans)] text-axiom-15 font-medium text-[#F0F2F8]">
          {label}
        </span>
        <span className="font-mono text-axiom-13 text-[#A0A8BC]">{chain.total_actions} actions</span>
        <span className="font-mono text-axiom-13 text-[#6B7490]">
          {chain.authorized} authorized · {chain.held} held · {chain.denied} denied
        </span>
        <span className="ml-auto font-mono text-axiom-13 text-[#34D399]">
          {Math.round(chain.compliance_rate)}% compliant
        </span>
      </button>
      {open ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-left">
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.receiptId}
                  className="border-t border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)]"
                >
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-axiom-13 text-[#A0A8BC]">
                    {row.time}
                  </td>
                  <td className="px-4 py-2 font-mono text-axiom-13 text-[#F0F2F8]">{row.agent}</td>
                  <td className="px-4 py-2 font-mono text-axiom-13 text-[#A0A8BC]">{row.action}</td>
                  <td className="max-w-[200px] truncate px-4 py-2 font-mono text-axiom-13 text-[#A0A8BC]">
                    {row.target}
                  </td>
                  <td className="px-4 py-2">
                    <VerdictBadge verdict={row.verdict} />
                  </td>
                  <td className="px-4 py-2">
                    <VerificationBadge status={row.verification} />
                  </td>
                  <td className="px-4 py-2">
                    <Link
                      href={`/dashboard/ledger/${row.receiptId}`}
                      className="font-mono text-axiom-13 text-[var(--axiom-electric)] underline-offset-2 hover:underline"
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
