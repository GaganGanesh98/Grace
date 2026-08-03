import type { VerdictCode } from "@/lib/governance-types";

export function formatRecordId(uuid: string): string {
  const hex = uuid.replace(/-/g, "");
  return `GR-${hex.slice(0, 6)}`;
}

export type UiVerdict = "AUTHORIZED" | "HELD" | "DENIED";

export function toUiVerdict(v: VerdictCode): UiVerdict {
  if (v === "allow") {
    return "AUTHORIZED";
  }
  if (v === "hold") {
    return "HELD";
  }
  if (v === "deny") {
    return "DENIED";
  }
  return "HELD";
}

export type UiVerification = "COMPLIANT" | "NON-COMPLIANT" | "PENDING";

export function toUiVerification(status: string, sealed: boolean): UiVerification {
  if (!sealed) {
    return "PENDING";
  }
  if (status === "pass") {
    return "COMPLIANT";
  }
  if (status === "fail") {
    return "NON-COMPLIANT";
  }
  return "PENDING";
}

export function truncateMiddle(s: string, max = 48): string {
  if (s.length <= max) {
    return s;
  }
  const half = Math.floor((max - 3) / 2);
  return `${s.slice(0, half)}…${s.slice(-half)}`;
}
