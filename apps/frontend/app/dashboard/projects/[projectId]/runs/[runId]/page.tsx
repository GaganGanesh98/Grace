"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactElement } from "react";
import { toast } from "sonner";

import { LiveRunView } from "@/components/runs/live-run-view";
import { ArtifactsGrid } from "@/components/runs/artifacts-grid";
import { useAgentRun } from "@/hooks/use-agent-runs";
import { useRunWebSocket } from "@/hooks/use-run-websocket";
import { mintAgentRunWsToken } from "@/lib/agent-runner-api";

export default function AgentRunDetailPage(): ReactElement {
  const params = useParams<{ projectId: string; runId: string }>();
  const projectId = params.projectId;
  const runId = params.runId;
  const runQ = useAgentRun(projectId, runId);
  const [token, setToken] = useState<string | null>(null);
  const ws = useRunWebSocket(runId, token);

  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const fromStorage =
          typeof window !== "undefined" ? sessionStorage.getItem(`axiom:ws:${runId}`) : null;
        if (fromStorage) {
          sessionStorage.removeItem(`axiom:ws:${runId}`);
          if (!cancelled) {
            setToken(fromStorage);
          }
          return;
        }
        const t = await mintAgentRunWsToken(projectId, runId);
        if (!cancelled) {
          setToken(t.token);
        }
      } catch (e) {
        if (!cancelled) {
          toast.error(e instanceof Error ? e.message : "Could not open stream");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId, runId]);

  const run = runQ.data;

  const artifactPaths = (() => {
    const fo = run?.final_output;
    if (!fo || typeof fo !== "object") {
      return [] as string[];
    }
    const paths: string[] = [];
    const ft = (fo as { file_writes?: unknown }).file_writes;
    if (Array.isArray(ft)) {
      for (const x of ft) {
        if (typeof x === "string") {
          paths.push(x);
        }
      }
    }
    return paths;
  })();

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/projects/${projectId}/agent-definitions`}
        className="font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-electric)] hover:underline"
      >
        ← Agents
      </Link>

      {runQ.isPending ? (
        <div className="h-40 animate-pulse rounded-lg bg-[#0A0A14]" />
      ) : runQ.error ? (
        <p className="text-red-400">{runQ.error.message}</p>
      ) : !run ? (
        <p className="text-[#6B7490]">Not found.</p>
      ) : (
        <>
          <div>
            <p className="font-mono text-axiom-11 uppercase text-[#6B7490]">Run</p>
            <h1 className="mt-2 break-all font-mono text-axiom-18 text-[#F0F2F8]">{run.id}</h1>
            <p className="mt-2 font-mono text-axiom-13 uppercase text-[#A0A8BC]">Status: {run.status}</p>
          </div>

          {!token ? (
            <p className="font-mono text-axiom-13 text-[#6B7490]">Connecting stream…</p>
          ) : (
            <LiveRunView run={run} ws={ws} />
          )}

          <section>
            <h2 className="font-mono text-axiom-12 uppercase tracking-[2px] text-[#6B7490]">Artifacts</h2>
            <div className="mt-3">
              <ArtifactsGrid paths={artifactPaths} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
