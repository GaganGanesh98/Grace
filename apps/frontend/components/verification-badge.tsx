import type { ReactElement } from "react";

import type { UiVerification } from "@/lib/governance-display";
import { cn } from "@/lib/utils";

const styles: Record<UiVerification, string> = {
  COMPLIANT: "border-emerald-500/40 bg-emerald-500/10 text-[#34D399]",
  "NON-COMPLIANT": "border-red-500/40 bg-red-500/10 text-[#F87171]",
  PENDING: "border-status-neutral-border bg-status-neutral-bg text-status-neutral-fg",
};

export function VerificationBadge({
  status,
  className,
}: {
  status: UiVerification;
  className?: string;
}): ReactElement {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-2 py-0.5 font-mono text-axiom-13 font-medium uppercase tracking-wide",
        styles[status],
        className,
      )}
    >
      {status === "PENDING" ? "PENDING" : status}
    </span>
  );
}
