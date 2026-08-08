"use client";

import { type ReactElement } from "react";

import { useGraceEventsContext } from "@/lib/events/grace-events-context";
import { cn } from "@/lib/utils";

import type { GraceEventsStatus } from "@/lib/events/event-types";

function tooltipFor(st: GraceEventsStatus): string {
  if (st === "connected") {
    return "Live updates connected";
  }
  if (st === "reconnecting") {
    return "Reconnecting...";
  }
  if (st === "disconnected") {
    return "Disconnected — click to retry";
  }
  return "Connecting...";
}

export function ConnectionIndicator(): ReactElement {
  const { status, showIndicator, connect } = useGraceEventsContext();

  if (!showIndicator) {
    return <div className="h-0 w-0" aria-hidden />;
  }

  const isConnected = status === "connected";
  const isDisconnected = status === "disconnected";

  const onClick: () => void =
    status === "disconnected"
      ? () => {
          connect();
        }
      : () => {};

  return (
    <div className="flex w-full items-center justify-center border-t border-[var(--axiom-border)] py-1.5">
      <span className="sr-only">{tooltipFor(status)}</span>
      <button
        type="button"
        title={tooltipFor(status)}
        onClick={onClick}
        disabled={status !== "disconnected"}
        className={cn(
          "flex h-4 w-4 items-center justify-center rounded-full p-0",
          isDisconnected ? "cursor-pointer" : "cursor-default",
        )}
        aria-label={tooltipFor(status)}
      >
        <span
          className={cn(
            isConnected && "live-dot",
            status === "reconnecting" && "h-2 w-2 rounded-pill bg-status-held-fg",
            isDisconnected && "h-2 w-2 rounded-pill bg-neutral-500",
          )}
        />
      </button>
    </div>
  );
}
