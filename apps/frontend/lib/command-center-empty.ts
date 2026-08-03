/** Pure helpers for Command Center empty state (7.5.2). */

const MS_30D = 30 * 24 * 60 * 60 * 1000;

export function isRecordInLast30Days(iso: string): boolean {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) {
    return false;
  }
  return Date.now() - t <= MS_30D;
}

/**
 * True when the active project has zero non-archived agent definitions and
 * zero governance records in the last 30 days (by intent created_at on each record).
 */
export function isCommandCenterEmptyState(
  agentDefinitionsCount: number,
  recordCreatedAtTimestamps: string[],
): boolean {
  const in30 = recordCreatedAtTimestamps.filter(isRecordInLast30Days);
  return agentDefinitionsCount === 0 && in30.length === 0;
}

export function getDurationLabel(execution: Record<string, unknown> | null | undefined): string {
  if (!execution || typeof execution !== "object") {
    return "—";
  }
  const c = execution as Record<string, unknown>;
  const raw = c.duration_ms ?? c.durationMs ?? c.latency_ms;
  if (raw == null || (typeof raw !== "number" && typeof raw !== "string")) {
    return "—";
  }
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) {
    return "—";
  }
  if (n < 1000) {
    return `${Math.round(n)}ms`;
  }
  return `${(n / 1000).toFixed(1)}s`;
}

export function verdictDisplay(verdict: string | null | undefined): { label: string; tone: "ok" | "bad" | "hold" } {
  const v = (verdict ?? "").toLowerCase();
  if (v === "allow" || v === "approve" || v === "authorized") {
    return { label: "AUTHORIZED", tone: "ok" };
  }
  if (v === "deny" || v === "block" || v === "denied" || v === "blocked") {
    return { label: "BLOCKED", tone: "bad" };
  }
  if (v === "hold" || v === "escalate" || v === "escalated") {
    return { label: "ESCALATED", tone: "hold" };
  }
  return { label: (verdict && verdict.length > 0 ? verdict : "—").toUpperCase(), tone: "hold" };
}
