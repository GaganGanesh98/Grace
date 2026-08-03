"use client";

import type { ReactElement } from "react";

import { ExecutionTimeline } from "@/components/runs/execution-timeline";
import { ResultsView } from "@/components/runs/results-view";
import type { useRunWebSocket } from "@/hooks/use-run-websocket";
import type { AgentRunOut } from "@/lib/types";

type LiveRunViewProps = {
  run: AgentRunOut;
  ws: ReturnType<typeof useRunWebSocket>;
};

const terminal = new Set(["succeeded", "failed", "cancelled"]);

export function LiveRunView({ run, ws }: LiveRunViewProps): ReactElement {
  const done = terminal.has(run.status);

  return (
    <div className="space-y-8">
      <section>
        <h2 className="font-mono text-axiom-12 uppercase tracking-[2px] text-[#6B7490]">Live execution</h2>
        {ws.errorMessage ? (
          <p className="mt-2 text-axiom-14 text-red-400">{ws.errorMessage}</p>
        ) : null}
        {ws.closeCode === 4401 ? (
          <p className="mt-2 text-axiom-14 text-red-400">WebSocket rejected (4401).</p>
        ) : null}
        <div className="mt-4">
          <ExecutionTimeline events={ws.events} />
        </div>
      </section>

      {done ? (
        <section>
          <h2 className="font-mono text-axiom-12 uppercase tracking-[2px] text-[#6B7490]">Results</h2>
          <div className="mt-4">
            <ResultsView run={run} />
          </div>
        </section>
      ) : (
        <p className="font-mono text-axiom-13 uppercase tracking-wide text-[#6B7490]">Run in progress…</p>
      )}
    </div>
  );
}
