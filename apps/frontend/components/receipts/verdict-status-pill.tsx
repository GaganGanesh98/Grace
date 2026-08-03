"use client";

import type { ReactElement } from "react";

import type { ReceiptVerdict } from "@/lib/receipts-api";
import { cn } from "@/lib/utils";

const verdictStyles: Record<
  ReceiptVerdict,
  { dot: string; border: string; bg: string; fg: string }
> = {
  AUTHORIZED: {
    dot: "bg-status-ok-fg",
    border: "border-status-ok-border",
    bg: "bg-status-ok-bg",
    fg: "text-status-ok-fg",
  },
  DENIED: {
    dot: "bg-status-denied-fg",
    border: "border-status-denied-border",
    bg: "bg-status-denied-bg",
    fg: "text-status-denied-fg",
  },
  HELD: {
    dot: "bg-status-held-fg",
    border: "border-status-held-border",
    bg: "bg-status-held-bg",
    fg: "text-status-held-fg",
  },
};

export function VerdictStatusPill({
  verdict,
  className,
}: {
  verdict: ReceiptVerdict;
  className?: string;
}): ReactElement {
  const s = verdictStyles[verdict];
  return (
    <span
      className={cn(
        "inline-flex min-w-[64px] items-center rounded-xs border px-2 py-0.5 text-micro",
        s.border,
        s.bg,
        s.fg,
        className,
      )}
    >
      <span className={cn("mr-1.5 h-1.5 w-1.5 shrink-0 rounded-pill", s.dot)} aria-hidden />
      {verdict}
    </span>
  );
}
