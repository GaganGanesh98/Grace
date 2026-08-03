"use client";

import Link from "next/link";
import type { ReactElement } from "react";

import type { AgentRunOut } from "@/lib/types";

type ResultsViewProps = {
  run: AgentRunOut;
};

function durationMs(run: AgentRunOut): string {
  if (!run.started_at || !run.completed_at) {
    return "—";
  }
  const a = new Date(run.started_at).getTime();
  const b = new Date(run.completed_at).getTime();
  if (Number.isNaN(a) || Number.isNaN(b)) {
    return "—";
  }
  return `${Math.max(0, b - a)} ms`;
}

export function ResultsView({ run }: ResultsViewProps): ReactElement {
  const fin = run.final_output;
  const text =
    fin && typeof fin === "object" && fin !== null && "final_text" in fin
      ? String((fin as { final_text?: unknown }).final_text ?? "")
      : "";
  const receiptIds =
    fin && typeof fin === "object" && fin !== null && "receipt_ids" in fin
      ? ((fin as { receipt_ids?: unknown }).receipt_ids as unknown[])
      : [];

  return (
    <div className="space-y-4 rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0A0A14] p-6">
      <div>
        <p className="font-mono text-axiom-11 uppercase tracking-wide text-[#6B7490]">Status</p>
        <p className="mt-1 font-mono text-axiom-16 text-[#F0F2F8]">{run.status}</p>
        {run.error_message ? (
          <p className="mt-2 text-axiom-14 text-red-400">{run.error_message}</p>
        ) : null}
      </div>

      <div>
        <p className="font-mono text-axiom-11 uppercase tracking-wide text-[#6B7490]">Final answer</p>
        <p className="mt-2 whitespace-pre-wrap text-axiom-15 text-[#F0F2F8]">{text || "—"}</p>
      </div>

      <div>
        <p className="font-mono text-axiom-11 uppercase tracking-wide text-[#6B7490]">Receipts</p>
        <ul className="mt-2 space-y-1">
          {Array.isArray(receiptIds) && receiptIds.length > 0 ? (
            receiptIds.map((rid) => (
              <li key={String(rid)}>
                <Link
                  href={`/dashboard/ledger/${encodeURIComponent(String(rid))}`}
                  className="font-mono text-axiom-14 text-[var(--axiom-electric)] hover:underline"
                >
                  {String(rid)}
                </Link>
              </li>
            ))
          ) : (
            <li className="text-axiom-14 text-[#6B7490]">—</li>
          )}
        </ul>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="font-mono text-axiom-11 uppercase tracking-wide text-[#6B7490]">Duration</p>
          <p className="mt-1 font-mono text-axiom-14 text-[#F0F2F8]">{durationMs(run)}</p>
        </div>
        <div>
          <p className="font-mono text-axiom-11 uppercase tracking-wide text-[#6B7490]">Correlation</p>
          <p className="mt-1 break-all font-mono text-axiom-12 text-[#A0A8BC]">{run.correlation_id}</p>
        </div>
      </div>

      {run.status === "cancelled" && run.completed_at ? (
        <p className="font-mono text-axiom-13 text-[#A0A8BC]">Cancelled at {run.completed_at}</p>
      ) : null}
    </div>
  );
}
