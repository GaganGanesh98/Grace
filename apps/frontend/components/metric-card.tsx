import type { ReactElement, ReactNode } from "react";

import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}): ReactElement {
  return (
    <div
      className={cn(
        "rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0A0A14] px-5 py-4",
        className,
      )}
    >
      <div className="font-mono text-axiom-13 font-normal uppercase tracking-wide text-[#A0A8BC]">
        {label}
      </div>
      <div className="mt-2 text-axiom-28 font-medium leading-none text-[#F0F2F8]">{children}</div>
    </div>
  );
}
