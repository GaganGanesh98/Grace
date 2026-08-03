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
        "overflow-x-auto rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#04040a] p-4 font-mono text-axiom-13 leading-relaxed text-[#A0A8BC]",
        className,
      )}
    >
      <code>{children}</code>
    </pre>
  );
}
