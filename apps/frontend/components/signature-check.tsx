import type { ReactElement } from "react";

import { cn } from "@/lib/utils";

export function SignatureCheck({
  label,
  ok,
  className,
}: {
  label: string;
  ok: boolean;
  className?: string;
}): ReactElement {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card px-4 py-3",
        className,
      )}
    >
      <div className="font-mono text-axiom-13 uppercase tracking-wide text-text-secondary">{label}</div>
      <div className={cn("mt-1 font-mono text-axiom-15", ok ? "text-status-ok-fg" : "text-status-denied-fg")}>
        {ok ? "✓ valid" : "✗ invalid"}
      </div>
    </div>
  );
}
