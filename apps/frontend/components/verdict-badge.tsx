import type { ReactElement } from "react";

import type { UiVerdict } from "@/lib/governance-display";
import { cn } from "@/lib/utils";

const styles: Record<UiVerdict, string> = {
  AUTHORIZED: "border-emerald-500/40 bg-emerald-500/10 text-[#34D399]",
  HELD: "border-amber-500/40 bg-amber-500/10 text-[#FBBF24]",
  DENIED: "border-red-500/40 bg-red-500/10 text-[#F87171]",
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
