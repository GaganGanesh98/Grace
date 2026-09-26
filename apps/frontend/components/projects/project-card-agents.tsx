import Link from "next/link";
import type { ReactElement } from "react";

type ReceiptAgent = { id: string; actions: number; last: string };

export type ProjectCardAgentsSectionProps = {
  projectId: string;
  /** Resolved non-archived definition total, or "…" while the count query is pending. */
  definitionCount: number | "…";
  isActive: boolean;
  receiptAgents: ReceiptAgent[];
};

/**
 * Projects page: agent definition count (Phase 6.5) plus optional governance receipt activity.
 */
export function ProjectCardAgentsSection({
  projectId,
  definitionCount,
  isActive,
  receiptAgents,
}: ProjectCardAgentsSectionProps): ReactElement {
  return (
    <div className="px-4 py-4">
      <h3 className="font-mono text-axiom-13 font-medium uppercase tracking-[1px] text-text-secondary">
        AGENTS ({definitionCount === "…" ? "…" : definitionCount})
      </h3>
      {definitionCount === "…" ? (
        <div className="mt-3 h-4 w-32 max-w-full animate-pulse rounded bg-secondary" aria-hidden />
      ) : definitionCount === 0 ? (
        <p className="mt-3 text-axiom-14 text-text-tertiary">No agents yet.</p>
      ) : (
        <p className="mt-3 text-axiom-14 text-text-tertiary">
          <Link
            href={`/dashboard/projects/${projectId}/agent-definitions`}
            className="text-[var(--axiom-electric)] hover:underline"
          >
            Open Agents
          </Link>{" "}
          to run or edit.
        </p>
      )}
      {isActive ? (
        <>
          <h4 className="mt-6 font-mono text-axiom-11 font-medium uppercase tracking-[1px] text-text-tertiary">
            Governance activity
          </h4>
          <ul className="mt-4 space-y-3">
            {receiptAgents.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center justify-between gap-2 font-mono text-axiom-13"
              >
                <span className="text-text-primary">{a.id}</span>
                <span className="text-text-secondary">
                  {a.actions} actions · {a.last}
                </span>
              </li>
            ))}
            {receiptAgents.length === 0 ? (
              <li className="text-axiom-14 text-text-tertiary">No governance receipts indexed yet.</li>
            ) : null}
          </ul>
        </>
      ) : (
        <p className="mt-3 text-axiom-14 text-text-tertiary">
          Set this project as active to load governance activity from receipts.
        </p>
      )}
    </div>
  );
}
