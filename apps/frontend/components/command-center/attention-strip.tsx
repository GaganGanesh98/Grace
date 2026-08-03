"use client";

import Link from "next/link";
import { type ReactElement } from "react";

import { cn } from "@/lib/utils";

export type AttentionStripProps = {
  pendingCount: number;
  oldestLabel: string;
  reviewHref: string;
  className?: string;
};

/**
 * Only mount when `pendingCount > 0` (parent omits from DOM when count is 0). Phase 6.5 review entry point.
 */
export function AttentionStrip({ pendingCount, oldestLabel, reviewHref, className }: AttentionStripProps): ReactElement {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-md border border-[var(--axiom-border)] border-l-2 border-l-[var(--axiom-warn)] bg-[var(--axiom-bg-card)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-2.5 sm:items-center">
        <span
          className="mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full bg-[var(--axiom-warn)] sm:mt-0"
          aria-hidden
        />
        <p className="min-w-0 text-axiom-14 text-[var(--axiom-text)]">
          <span className="font-medium">{pendingCount} approvals pending</span>{" "}
          <span className="text-[var(--axiom-text-muted)]">
            oldest {oldestLabel} · review before timeout
          </span>
        </p>
      </div>
      <div className="shrink-0">
        <Link
          className="inline-flex items-center justify-center rounded-sm border border-border bg-transparent px-3 py-2 font-mono text-axiom-12 font-semibold tracking-wide text-text-primary outline-none transition-colors hover:bg-surface-elevated focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
          href={reviewHref}
        >
          REVIEW →
        </Link>
      </div>
    </div>
  );
}
