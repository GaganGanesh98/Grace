"use client";

import Link from "next/link";
import { useCallback, type ReactElement, type KeyboardEvent } from "react";

import { verdictDisplay } from "@/lib/command-center-empty";
import { formatDurationMs } from "@/lib/format/format-duration";
import type { GovernanceReceiptRecord } from "@/lib/governance-types";
import { cn } from "@/lib/utils";

function formatTimeShort(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) {
    return "—";
  }
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 60) {
    return `${s}s ago`;
  }
  if (s < 3600) {
    return `${Math.floor(s / 60)}m ago`;
  }
  if (s < 86400) {
    return `${Math.floor(s / 3600)}h ago`;
  }
  return `${Math.floor(s / 86400)}d ago`;
}

function displayReceiptId(id: string): string {
  if (id.length <= 14) {
    return id;
  }
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

function truncateAgentId(id: string): string {
  if (id.length <= 14) {
    return id;
  }
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

export type AgentNameLoadState = "loading" | "ready" | "error";

export type ActivityTableProps = {
  rows: GovernanceReceiptRecord[];
  onRowSelect: (receiptId: string) => void;
  agentsLinkHref: string;
  /** agent_id (UUID) → display name from agent definitions; built once per project. */
  agentNameById?: ReadonlyMap<string, string> | null;
  agentNameLoadState?: AgentNameLoadState;
};

export function ActivityTable({
  rows,
  onRowSelect,
  agentsLinkHref,
  agentNameById = null,
  agentNameLoadState = "ready",
}: ActivityTableProps): ReactElement {
  const onRowKeyDown = useCallback(
    (e: KeyboardEvent, id: string) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onRowSelect(id);
      }
    },
    [onRowSelect],
  );

  return (
    <div
      className="w-full min-w-0 max-w-full overflow-x-auto"
      data-testid="cc-activity-table"
    >
      <table className="w-full min-w-[800px] border-separate border-spacing-0 text-left text-axiom-12 tabular-nums">
        <caption className="sr-only">Recent governance activity for this project</caption>
        <thead>
          <tr className="h-8 border-b border-[var(--axiom-border)] text-[var(--axiom-text-label)]">
            <th scope="col" className="pb-2.5 pl-0 pr-2 text-left font-mono text-axiom-11">
              Time
            </th>
            <th scope="col" className="pb-2.5 px-2 text-left font-mono text-axiom-11">
              Agent
            </th>
            <th scope="col" className="pb-2.5 px-2 text-left font-mono text-axiom-11">
              Action
            </th>
            <th scope="col" className="pb-2.5 px-2 text-left font-mono text-axiom-11">
              Receipt
            </th>
            <th scope="col" className="pb-2.5 px-2 text-left font-mono text-axiom-11">
              Verdict
            </th>
            <th
              scope="col"
              className="pb-2.5 pl-2 pr-0 text-right font-mono text-axiom-11"
            >
              Dur
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={6} className="py-10 text-center text-axiom-14 text-[var(--axiom-text-muted)]">
                No activity yet — submit your first agent run →{" "}
                <Link
                  className="text-[var(--axiom-electric)] underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
                  href={agentsLinkHref}
                >
                  /dashboard/agents
                </Link>
              </td>
            </tr>
          ) : (
            rows.map((r) => {
              const { label, tone } = verdictDisplay(r.verdict.verdict);
              const bgChip =
                tone === "ok"
                  ? "bg-[rgba(109,184,98,0.15)] text-[var(--axiom-success)]"
                  : tone === "bad"
                    ? "bg-[rgba(224,80,80,0.12)] text-[var(--axiom-danger)]"
                    : "bg-[rgba(212,160,48,0.12)] text-[var(--axiom-warn)]";
              return (
                <tr
                  key={r.id}
                  data-receipt-row={r.id}
                  className="group/row h-9 cursor-pointer border-b border-[var(--axiom-border)] transition-[background-color,border-color] duration-instant ease-default hover:bg-surface-elevated focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-100"
                  onClick={() => onRowSelect(r.id)}
                  onKeyDown={(e) => onRowKeyDown(e, r.id)}
                  role="button"
                  tabIndex={0}
                >
                  <td className="w-[1%] max-w-[88px] border-l-[3px] border-l-transparent py-2.5 pl-0 pr-2 font-mono text-axiom-12 text-[var(--axiom-text-muted)] transition-[background-color,border-color] duration-instant ease-default group-hover/row:border-l-text-primary group-hover/row:bg-surface-elevated">
                    {formatTimeShort(r.intent.created_at)}
                  </td>
                  <td className="min-w-0 max-w-[140px] truncate py-2.5 px-2 font-mono text-axiom-12 text-[var(--axiom-text)] group-hover/row:bg-surface-elevated">
                    {(() => {
                      const id = String(r.intent.agent_id ?? "").trim();
                      if (!id) {
                        return "—";
                      }
                      const short = truncateAgentId(id);
                      if (agentNameLoadState === "loading" || agentNameLoadState === "error") {
                        return short;
                      }
                      if (agentNameById) {
                        if (agentNameById.has(id)) {
                          const n = (agentNameById.get(id) ?? "").trim();
                          return n.length > 0 ? n : short;
                        }
                        return (
                          <span>
                            {short}{" "}
                            <span className="text-axiom-11 text-[var(--axiom-text-dim)]">(deleted)</span>
                          </span>
                        );
                      }
                      return short;
                    })()}
                  </td>
                  <td className="min-w-0 max-w-[220px] truncate py-2.5 px-2 font-mono text-axiom-12 text-[var(--axiom-text-muted)] group-hover/row:bg-surface-elevated">
                    {r.intent.action_type ?? r.intent.target ?? "—"}
                  </td>
                  <td className="min-w-0 max-w-[180px] py-2.5 px-2 group-hover/row:bg-surface-elevated">
                    <span className="font-mono text-axiom-12 text-[var(--axiom-electric)]" data-truncate-receipt>
                      {displayReceiptId(r.id)}
                    </span>
                  </td>
                  <td className="py-2.5 px-2 group-hover/row:bg-surface-elevated">
                    <span
                      className={cn(
                        "inline-flex rounded-xs px-2 py-0.5 font-mono text-axiom-11",
                        bgChip,
                      )}
                    >
                      {label}
                    </span>
                  </td>
                  <td className="whitespace-nowrap py-2.5 pl-2 pr-0 text-right font-mono text-axiom-12 text-[var(--axiom-text-muted)] group-hover/row:bg-surface-elevated">
                    {formatDurationMs(r.duration_ms)}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
