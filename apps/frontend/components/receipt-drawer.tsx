"use client";

import { Check, Copy, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, type ReactElement } from "react";

import { VerdictBadge } from "@/components/verdict-badge";
import { Button } from "@/components/ui/button";
import { fetchAgentRuns } from "@/lib/agent-runner-api";
import { parseApiError } from "@/lib/api";
import type { AgentRunArtifact } from "@/lib/types";
import { toUiVerdict } from "@/lib/governance-display";

export type CommandCenterReceiptDetail = {
  receipt_id: string;
  verdict: string;
  action_type: string;
  timestamp: string;
  signatures: {
    ed25519: { signature: string; verified: boolean };
    ml_dsa_65: { signature: string; verified: boolean };
  };
  merkle: { leaf_index: number | null; depth: number; root_hash: string };
  tsa: { timestamp?: string | null; verified: boolean; authority?: string };
  pipeline: Array<{
    stage: number;
    name: string;
    outcome: string;
    evidence: Record<string, unknown>;
  }>;
  request_preview: string;
  response_preview: string;
};

type ReceiptDrawerProps = {
  receiptId: string | null;
  projectId: string | null;
  onClose: () => void;
  returnFocusSelector?: string | null;
};

function truncateHash(hex: string, keep = 10): string {
  if (!hex || hex.length <= keep + 4) {
    return hex;
  }
  return `${hex.slice(0, keep)}…`;
}

export function ReceiptDrawer({
  receiptId,
  projectId,
  onClose,
  returnFocusSelector,
}: ReceiptDrawerProps): ReactElement | null {
  const panelId = useId();
  const [detail, setDetail] = useState<CommandCenterReceiptDetail | null>(null);
  const [artifacts, setArtifacts] = useState<AgentRunArtifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; diagnostic?: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (): Promise<void> => {
    if (!receiptId || !projectId) {
      return;
    }
    setLoading(true);
    setError(null);
    setDetail(null);
    setArtifacts([]);
    try {
      const qs = `project_id=${encodeURIComponent(projectId)}`;
      const res = await fetch(`/api/receipts/${encodeURIComponent(receiptId)}?${qs}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        setError({
          message: err.message,
          diagnostic: `receipt_id=${receiptId} · attempted GET /api/receipts/${receiptId}`,
        });
        setLoading(false);
        return;
      }
      const body = (await res.json()) as CommandCenterReceiptDetail;
      setDetail(body);

      try {
        const runs = await fetchAgentRuns(projectId);
        const merged: AgentRunArtifact[] = [];
        for (const run of runs) {
          if (run.receipt_ids?.includes(receiptId) && run.artifacts?.length) {
            merged.push(...run.artifacts);
          }
        }
        setArtifacts(merged);
      } catch {
        setArtifacts([]);
      }
    } catch (e: unknown) {
      setError({
        message: e instanceof Error ? e.message : "Failed to load receipt",
        diagnostic: `receipt_id=${receiptId}`,
      });
    } finally {
      setLoading(false);
    }
  }, [receiptId, projectId]);

  const handleClose = useCallback(() => {
    onClose();
    if (returnFocusSelector) {
      requestAnimationFrame(() => {
        const el = document.querySelector<HTMLElement>(returnFocusSelector);
        el?.focus();
      });
    }
  }, [onClose, returnFocusSelector]);

  useEffect(() => {
    if (receiptId && projectId) {
      void load();
    }
  }, [receiptId, projectId, load]);

  useEffect(() => {
    if (!receiptId) {
      return;
    }
    function onKey(ev: KeyboardEvent): void {
      if (ev.key === "Escape") {
        handleClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [receiptId, handleClose]);

  useEffect(() => {
    if (receiptId) {
      panelRef.current?.focus();
    }
  }, [receiptId]);

  if (!receiptId) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[60] flex justify-end" aria-modal="true" role="dialog" aria-labelledby={panelId}>
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Close drawer"
        onClick={handleClose}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className="relative flex h-full w-full max-w-[520px] flex-col border-l border-[rgba(255,255,255,0.08)] bg-[#0A0A14] shadow-2xl outline-none"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-5 py-4">
          <h2 id={panelId} className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
            Governance receipt
          </h2>
          <Button type="button" variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={handleClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[rgba(255,255,255,0.04)]" />
              ))}
            </div>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-[rgba(248,113,113,0.35)] bg-[rgba(248,113,113,0.08)] p-4">
              <p className="font-mono text-axiom-13 font-medium text-[#F87171]">Could not load receipt</p>
              <p className="mt-2 font-mono text-axiom-13 text-[#A0A8BC]">{error.message}</p>
              {error.diagnostic ? (
                <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap break-all font-mono text-axiom-12 text-[#6B7490]">
                  {error.diagnostic}
                </pre>
              ) : null}
            </div>
          ) : null}

          {!loading && !error && detail ? (
            <div className="space-y-6">
              <div className="flex flex-wrap items-center gap-2">
                <VerdictBadge verdict={toUiVerdict(detail.verdict)} />
                <span className="font-mono text-axiom-12 text-[#6B7490]">{detail.action_type}</span>
              </div>

              <section>
                <h3 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
                  Receipt ID
                </h3>
                <div className="mt-2 flex items-start gap-2">
                  <code className="break-all font-mono text-axiom-13 text-[#A0A8BC]">{detail.receipt_id}</code>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 shrink-0 px-2"
                    onClick={() => {
                      void navigator.clipboard.writeText(detail.receipt_id);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }}
                  >
                    {copied ? <Check className="h-3.5 w-3.5 text-[#34D399]" /> : <Copy className="h-3.5 w-3.5" />}
                  </Button>
                </div>
              </section>

              <section className="rounded-lg border border-[rgba(255,255,255,0.06)] p-4">
                <h3 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
                  Signatures
                </h3>
                <div className="mt-3 grid grid-cols-2 gap-3 font-mono text-axiom-13 text-[#A0A8BC]">
                  <div>
                    Ed25519{" "}
                    <span className={detail.signatures.ed25519.verified ? "text-[#34D399]" : "text-[#F87171]"}>
                      {detail.signatures.ed25519.verified ? "✓ verified" : "✗"}
                    </span>
                  </div>
                  <div>
                    ML-DSA-65{" "}
                    <span className={detail.signatures.ml_dsa_65.verified ? "text-[#34D399]" : "text-[#F87171]"}>
                      {detail.signatures.ml_dsa_65.verified ? "✓ verified" : "✗"}
                    </span>
                  </div>
                </div>
              </section>

              <section className="rounded-lg border border-[rgba(255,255,255,0.06)] p-4">
                <h3 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">Merkle</h3>
                <p
                  className="mt-2 font-mono text-axiom-13 text-[#A0A8BC]"
                  title={detail.merkle.root_hash || undefined}
                >
                  Leaf #{detail.merkle.leaf_index ?? "—"} · Depth {detail.merkle.depth} · Root{" "}
                  {truncateHash(detail.merkle.root_hash)}
                </p>
              </section>

              <section className="rounded-lg border border-[rgba(255,255,255,0.06)] p-4">
                <h3 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
                  RFC 3161 timestamp
                </h3>
                <p className="mt-2 font-mono text-axiom-13 text-[#A0A8BC]">
                  {detail.tsa.verified ? "✓" : "—"} · {detail.tsa.timestamp ?? "—"} · Authority:{" "}
                  {detail.tsa.authority ?? "—"}
                </p>
              </section>

              <section>
                <h3 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
                  Governance pipeline
                </h3>
                <ol className="mt-3 list-decimal space-y-3 pl-5 font-mono text-axiom-13 text-[#A0A8BC]">
                  {detail.pipeline.map((st) => (
                    <li key={st.stage} className="marker:text-[var(--axiom-electric)]">
                      <div className="font-medium text-[#F0F2F8]">
                        {st.stage}. {st.name}
                      </div>
                      <div className="text-axiom-13 text-[#A0A8BC]">{st.outcome}</div>
                      <details className="mt-1">
                        <summary className="cursor-pointer text-axiom-12 text-[#6B7490]">Evidence</summary>
                        <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-all text-axiom-12 text-[#6B7490]">
                          {JSON.stringify(st.evidence, null, 2)}
                        </pre>
                      </details>
                    </li>
                  ))}
                </ol>
              </section>

              <section>
                <h3 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
                  Artifacts
                </h3>
                {artifacts.length === 0 ? (
                  <p className="mt-2 font-mono text-axiom-13 text-[#6B7490]">No artifacts produced by this action</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {artifacts.map((a, i) => (
                      <li key={`${a.path}-${i}`}>
                        <a
                          href={a.url}
                          className="font-mono text-axiom-13 text-[var(--axiom-electric)] underline-offset-2 hover:underline"
                        >
                          {a.path}
                        </a>
                        <span className="ml-2 font-mono text-axiom-12 text-[#6B7490]">
                          {a.content_type} · {a.size_bytes} bytes
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <h3 className="font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">Previews</h3>
                <div className="mt-2 space-y-2">
                  <div>
                    <div className="font-mono text-axiom-12 uppercase tracking-wide text-[#6B7490]">Request</div>
                    <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-all font-mono text-axiom-13 text-[#A0A8BC]">
                      {detail.request_preview}
                    </pre>
                  </div>
                  <div>
                    <div className="font-mono text-axiom-12 uppercase tracking-wide text-[#6B7490]">Response</div>
                    <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-all font-mono text-axiom-13 text-[#A0A8BC]">
                      {detail.response_preview}
                    </pre>
                  </div>
                  <Button type="button" variant="secondary" size="sm" disabled className="mt-2">
                    View full (requires elevated grant)
                  </Button>
                </div>
              </section>
            </div>
          ) : null}
        </div>

        <footer className="shrink-0 border-t border-[rgba(255,255,255,0.06)] px-5 py-3">
          <Link
            href={`/dashboard/ledger/${encodeURIComponent(receiptId)}`}
            className="font-mono text-axiom-13 text-[var(--axiom-electric)] hover:underline"
          >
            Verify this receipt offline →
          </Link>
        </footer>
      </div>
    </div>
  );
}
