import type { ReactElement } from "react";

import { cn } from "@/lib/utils";

export function CodeBlock({
  children,
  className,
}: {
  children: string;
  className?: string;
}): ReactElement {
  return (
    <pre
      className={cn(
        "overflow-x-auto rounded-lg border border-border bg-[var(--surface-muted)] p-4 font-mono text-axiom-13 leading-relaxed text-text-secondary",
        className,
      )}
    >
      <code>{children}</code>
    </pre>
  );
}
