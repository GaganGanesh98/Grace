/**
 * Format a wall-clock duration in milliseconds (Phase 7.5.4 — Command Center Dur column).
 * Same-style helper as `humanize-age.ts`, but for a duration value, not relative "time ago".
 */

const MS_1M = 60_000;

/** <1000 → "{N}ms"; 1000–59999 → "{N.N}s"; 60000+ → "{N.N}m" (one decimal). */
export function formatDurationMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) {
    return "—";
  }
  const n = Math.round(ms);
  if (n < 1000) {
    return `${n}ms`;
  }
  if (n < MS_1M) {
    return `${(n / 1000).toFixed(1)}s`;
  }
  return `${(n / MS_1M).toFixed(1)}m`;
}
