import type { ReactElement } from "react";

import type { AgentRunOut } from "@/lib/types";

/**
 * Shown where a metric exists in the UI but nothing computes it yet.
 *
 * A bare em-dash reads as "zero" or "broken". This says which it is: the number
 * is not implemented, not absent. Replace the constant — not the individual
 * cells — when the aggregate lands.
 */
export const NOT_TRACKED = "Not tracked yet";

/** Run detail lives under the project, not under the ledger (which keys on receipt id). */
export function runDetailHref(projectId: string, runId: string): string {
  return `/dashboard/projects/${projectId}/runs/${runId}`;
}

const MAX_INLINE_ERROR = 120;

export function truncateError(message: string, max: number = MAX_INLINE_ERROR): string {
  const clean = message.trim().replace(/\s+/g, " ");
  if (clean.length <= max) {
    return clean;
  }
  return `${clean.slice(0, max - 1)}…`;
}

/**
 * The reason a run failed, inline on the row.
 *
 * `error_message` was persisted by the worker and returned by the API but only
 * rendered on the run detail page, so a failed run in a list was a red badge
 * with no way to tell why without clicking through.
 */
export function RunFailureReason({ run }: { run: AgentRunOut }): ReactElement | null {
  if (run.status !== "failed" || !run.error_message) {
    return null;
  }
  const full = run.error_message.trim();
  return (
    <span
      className="mt-0.5 block truncate text-axiom-11 text-red-400"
      title={full}
      data-testid="run-failure-reason"
    >
      {truncateError(full)}
    </span>
  );
}
