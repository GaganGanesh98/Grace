"use client";

import type { ReactElement } from "react";

import type { RunStreamEvent } from "@/hooks/use-run-websocket";
import { cn } from "@/lib/utils";

type ExecutionTimelineProps = {
  events: RunStreamEvent[];
};

function summarize(ev: RunStreamEvent): { title: string; detail?: string; variant: "default" | "deny" } {
  const t = String(ev.type ?? "event");
  if (t === "run_started") {
    return { title: "Run started", variant: "default" };
  }
  if (t === "run_finished" || t === "run_failed") {
    return { title: t === "run_finished" ? "Run finished" : "Run failed", variant: "default" };
  }
  if (t === "react_iteration") {
    return {
      title: `Iteration ${String(ev.iteration ?? "")}`,
      detail: `run ${String(ev.run_id ?? "")}`,
      variant: "default",
    };
  }
  if (t === "status_change") {
    return { title: `Status → ${String(ev.status ?? "")}`, variant: "default" };
  }
  const denied =
    typeof ev.content === "string" && ev.content.includes('"denied":true');
  return {
    title: t,
    detail: JSON.stringify(ev),
    variant: denied ? "deny" : "default",
  };
}

export function ExecutionTimeline({ events }: ExecutionTimelineProps): ReactElement {
  if (events.length === 0) {
    return (
      <p className="font-mono text-axiom-13 uppercase tracking-wide text-[#82878f]">
        Waiting for events…
      </p>
    );
  }

  return (
    <ol className="space-y-2 border-l border-border-subtle pl-4">
      {events.map((ev, i) => {
        const s = summarize(ev);
        return (
          <li key={`${s.title}-${i}`} className="relative">
            <span className="absolute -left-[21px] top-1.5 flex h-[18px] w-[18px] items-center justify-center rounded-pill border border-[var(--axiom-electric)] bg-[#08090b] font-mono text-axiom-10 text-[var(--axiom-electric)]">
              {(i + 1).toString().padStart(2, "0")}
            </span>
            <p
              className={cn(
                "font-mono text-axiom-13 uppercase tracking-wide",
                s.variant === "deny" ? "text-amber-400" : "text-[#ecedef]",
              )}
            >
              {s.title}
            </p>
            {s.detail ? (
              <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-all font-mono text-axiom-11 text-[#a8adb5]">
                {s.detail}
              </pre>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
