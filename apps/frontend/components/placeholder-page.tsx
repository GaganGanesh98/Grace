"use client";

import { useId, type ReactElement } from "react";

import { cn } from "@/lib/utils";

type PlaceholderPageProps = { title: string; className?: string };

/**
 * v0.8 placeholder shell for dashboard routes. Uses existing heading + muted caption patterns.
 */
export function PlaceholderPage({ title, className }: PlaceholderPageProps): ReactElement {
  const labelId = useId();
  return (
    <div
      className={cn("flex min-h-[50vh] flex-col items-center justify-center gap-6 text-center", className)}
      aria-labelledby={labelId}
    >
      <h1 id={labelId} className="text-axiom-24 font-medium text-[var(--axiom-text)]">
        {title}
      </h1>
      <div
        className="flex h-8 items-end gap-1.5"
        role="status"
        aria-label="Loading"
      >
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--axiom-text-muted)] [animation-delay:0ms]" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--axiom-text-muted)] [animation-delay:200ms]" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--axiom-text-muted)] [animation-delay:400ms]" />
      </div>
      <p className="text-axiom-15 text-[var(--axiom-text-muted)]">
        {title} is coming in v0.8
      </p>
    </div>
  );
}
