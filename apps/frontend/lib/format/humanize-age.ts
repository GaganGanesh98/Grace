/**
 * Humanize a duration in seconds to short form (TSA / footer): s / m / h / d.
 * <60s → "Ns", <60m → "Nm", <24h → "Nh", else → "Nd" (per Phase 7.5.3).
 */
export function humanizeShortDurationSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "0s";
  }
  const s = Math.floor(seconds);
  if (s < 60) {
    return `${s}s`;
  }
  if (s < 3600) {
    return `${Math.floor(s / 60)}m`;
  }
  if (s < 86400) {
    return `${Math.floor(s / 3600)}h`;
  }
  return `${Math.floor(s / 86400)}d`;
}
