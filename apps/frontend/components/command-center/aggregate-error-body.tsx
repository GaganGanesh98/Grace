"use client";

import { type ReactElement } from "react";

import { CommandCenterRequestError } from "@/lib/command-center-api";

export type AggregateErrorBodyProps = {
  error: Error | null;
  onRetry: () => void;
  /** true when 403 — per spec, no RETRY, different title */
  isForbidden?: boolean;
};

function statusForDisplay(error: Error, isForbidden: boolean): string {
  if (isForbidden) {
    return "403";
  }
  if (error instanceof CommandCenterRequestError && error.status > 0) {
    return String(error.status);
  }
  if (error instanceof CommandCenterRequestError) {
    return "network error";
  }
  return "network error";
}

export function AggregateErrorBody({ error, onRetry, isForbidden = false }: AggregateErrorBodyProps): ReactElement {
  if (!error) {
    return (
      <p className="text-axiom-15 text-[var(--axiom-text-muted)]" role="alert">
        Unknown error
      </p>
    );
  }
  if (isForbidden) {
    return (
      <div className="space-y-1" role="alert">
        <p className="text-axiom-14 text-[var(--axiom-text-muted)]">Insufficient permissions</p>
        <p className="text-axiom-11 text-[var(--axiom-text-dim)]">{statusForDisplay(error, true)}</p>
      </div>
    );
  }
  return (
    <div className="space-y-2" role="alert">
      <p className="text-axiom-14 text-[var(--axiom-text-muted)]">
        <span className="inline-block h-1.5 w-1.5 translate-y-px rounded-full bg-[#da1e28] align-middle" />
        <span className="ms-1.5">Couldn&apos;t load data</span>
      </p>
      <p className="text-axiom-11 text-[var(--axiom-text-dim)]">{statusForDisplay(error, false)}</p>
      <button
        type="button"
        className="font-mono text-axiom-12 text-[var(--axiom-electric)] hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
        onClick={() => {
          onRetry();
        }}
      >
        RETRY
      </button>
    </div>
  );
}
