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
        "rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0A0A14] px-4 py-3",
        className,
      )}
    >
      <div className="font-mono text-axiom-13 uppercase tracking-wide text-[#A0A8BC]">{label}</div>
      <div className={cn("mt-1 font-mono text-axiom-15", ok ? "text-[#34D399]" : "text-[#F87171]")}>
        {ok ? "✓ valid" : "✗ invalid"}
      </div>
    </div>
  );
}
