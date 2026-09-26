import type { ReactElement } from "react";

import type { UiVerdict } from "@/lib/governance-display";
import { cn } from "@/lib/utils";

const styles: Record<UiVerdict, string> = {
  AUTHORIZED: "border-emerald-500/40 bg-emerald-500/10 text-status-ok-fg",
  HELD: "border-amber-500/40 bg-amber-500/10 text-status-held-fg",
  DENIED: "border-red-500/40 bg-red-500/10 text-status-denied-fg",
};

export function VerdictBadge({
  verdict,
  className,
}: {
  verdict: UiVerdict;
  className?: string;
}): ReactElement {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-2 py-0.5 font-mono text-axiom-13 font-medium uppercase tracking-wide",
        styles[verdict],
        className,
      )}
    >
      {verdict}
    </span>
  );
}
