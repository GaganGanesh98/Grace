"use client";

import { type ReactElement } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { humanizeShortDurationSeconds } from "@/lib/format/humanize-age";
import { useTsaStatusQuery } from "@/lib/queries/command-center";
import { cn } from "@/lib/utils";

export type CryptoFooterProps = {
  projectId: string | null;
  merkleDepth: string | number;
  policyLabel: string;
  className?: string;
};

function merkleDepthLabel(merkleDepth: string | number): string {
  if (merkleDepth === "—" || merkleDepth === "–" || merkleDepth == null) {
    return "OK";
  }
  if (typeof merkleDepth === "number" && !Number.isNaN(merkleDepth)) {
    return String(merkleDepth);
  }
  if (typeof merkleDepth === "string" && merkleDepth.trim() !== "") {
    return merkleDepth;
  }
  return "OK";
}

export function CryptoFooter({ projectId, merkleDepth, policyLabel, className }: CryptoFooterProps): ReactElement {
  const tsa = useTsaStatusQuery({ projectId });
  const depthS = merkleDepthLabel(merkleDepth);
  const staticLine = `ED25519 + ML-DSA-65 | MERKLE DEPTH ${merkleDepth} | POLICY: ${policyLabel}`;

  if (!projectId) {
    return (
      <div
        className={cn(
          "mt-4 border-t border-[var(--axiom-border)] pt-4 font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-text-label)]",
          className,
        )}
      >
        {staticLine}
      </div>
    );
  }

  if (tsa.isPending) {
    return (
      <div
        className={cn(
          "mt-4 border-t border-[var(--axiom-border)] pt-4",
          className,
        )}
      >
        <Skeleton className="h-3.5 w-full max-w-3xl" />
      </div>
    );
  }

  const d = tsa.data;
  if (d == null) {
    return (
      <div
        className={cn(
          "mt-4 border-t border-[var(--axiom-border)] pt-4 font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-text-label)]",
          className,
        )}
      >
        {staticLine}
      </div>
    );
  }

  if (d.kind === "fallback") {
    return (
      <div
        className={cn(
          "mt-4 border-t border-[var(--axiom-border)] pt-4 font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-text-label)]",
          className,
        )}
      >
        {staticLine}
      </div>
    );
  }

  const tsaText =
    d.data.last_anchor_age_seconds == null
      ? "TSA NOT YET ANCHORED"
      : `TSA ANCHORED ${humanizeShortDurationSeconds(d.data.last_anchor_age_seconds)} AGO`;

  const line = `ED25519 + ML-DSA-65 · MERKLE DEPTH ${depthS} · ${tsaText}`;

  return (
    <div
      className={cn(
        "mt-4 border-t border-[var(--axiom-border)] pt-4 font-mono text-axiom-12 text-[var(--axiom-text-label)] tracking-wide",
        className,
      )}
    >
      {line}
    </div>
  );
}
