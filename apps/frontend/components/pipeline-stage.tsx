import type { ReactElement, ReactNode } from "react";

import { cn } from "@/lib/utils";

export function PipelineStage({
  index,
  title,
  children,
  className,
  showConnector = true,
}: {
  index: number;
  title: string;
  children: ReactNode;
  className?: string;
  showConnector?: boolean;
}): ReactElement {
  return (
    <div className={cn("relative pl-8", className)}>
      {showConnector ? (
        <div
          aria-hidden
          className="absolute bottom-0 left-[11px] top-8 w-px bg-border-subtle"
        />
      ) : null}
      <div className="absolute left-0 top-1 flex h-6 w-6 items-center justify-center rounded-pill border border-border-strong bg-[var(--surface-muted)] font-mono text-axiom-11 text-[var(--axiom-electric)]">
        {index}
      </div>
      <div className="mb-6 rounded-lg border border-border bg-[var(--surface-muted)] p-5">
        <h3 className="mb-4 font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-text-primary">
          {title}
        </h3>
        {children}
      </div>
    </div>
  );
}
