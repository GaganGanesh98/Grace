"use client";

import { Check, Copy, Loader2, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactElement } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { VerdictStatusPill } from "@/components/receipts/verdict-status-pill";
import { getReceipt, verifyReceipt, type ReceiptDetail } from "@/lib/receipts-api";
import { cn } from "@/lib/utils";

export type GovernanceReceiptDrawerProps = {
  receiptId: string | null;
  projectId: string | null;
  onClose: () => void;
};

function formatRelative(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) {
    return "—";
  }
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 60) {
    return `${s}s ago`;
  }
  if (s < 3600) {
    return `${Math.floor(s / 60)}m ago`;
  }
  if (s < 86400) {
    return `${Math.floor(s / 3600)}h ago`;
  }
  return `${Math.floor(s / 86400)}d ago`;
}

function shortHex(hex: string, head = 32, tail = 16): string {
  if (hex.length <= head + tail + 3) {
    return hex;
  }
  return `${hex.slice(0, head)}…${hex.slice(-tail)}`;
}

function byteLengthFromHex(hex: string): number {
  return Math.floor(hex.replace(/\s/g, "").length / 2);
}

function CryptoHexRow({
  label,
  standardNote,
  hex,
}: {
  label: string;
  standardNote: string;
  hex: string;
}): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const bytes = byteLengthFromHex(hex);
  const display = expanded || hex.length <= 52 ? hex : shortHex(hex);

  const copy = (): void => {
    if (!hex) {
      return;
    }
    void navigator.clipboard.writeText(hex);
    toast.success("Copied");
  };

  return (
    <div className="space-y-1.5 border-b border-[var(--border-subtle)] py-3 last:border-b-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <div className="text-body-s text-text-secondary">{label}</div>
          <div className="mt-0.5 text-mono-caption text-text-tertiary">
            {standardNote}
            {bytes > 0 ? ` · ${bytes} bytes` : ""}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hex.length > 52 ? (
            <button
              type="button"
              className="text-caption text-text-secondary underline decoration-border-strong underline-offset-2 hover:text-text-primary"
              onClick={() => setExpanded((e) => !e)}
            >
              {expanded ? "Collapse" : "Expand"}
            </button>
          ) : null}
          <button
            type="button"
            className="rounded-sm p-1 text-text-tertiary transition-colors hover:bg-surface-elevated hover:text-text-primary"
            aria-label={`Copy ${label}`}
            onClick={copy}
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <pre
        className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-sm bg-[var(--surface-code)] p-2 font-mono text-[11px] leading-snug text-text-primary tabular-nums"
        style={{ fontSize: "11px" }}
      >
        {display || "—"}
      </pre>
    </div>
  );
}

export function GovernanceReceiptDrawer({
  receiptId,
  projectId,
  onClose,
}: GovernanceReceiptDrawerProps): ReactElement | null {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const [displayId, setDisplayId] = useState<string | null>(null);
  const [slideIn, setSlideIn] = useState(false);
  const [detail, setDetail] = useState<ReceiptDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [verifyPending, setVerifyPending] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    valid: boolean;
    ed25519_valid: boolean;
    ml_dsa_valid: boolean;
    merkle_valid: boolean;
    errors: string[];
  } | null>(null);

  const closeAnimated = useCallback(() => {
    setSlideIn(false);
    window.setTimeout(() => {
      setDisplayId(null);
      setDetail(null);
      setLoadError(null);
      setVerifyResult(null);
      onClose();
    }, 120);
  }, [onClose]);

  useLayoutEffect(() => {
    if (receiptId) {
      setDisplayId(receiptId);
      setSlideIn(true);
    }
  }, [receiptId]);

  useEffect(() => {
    if (!receiptId && displayId) {
      setSlideIn(false);
      const t = window.setTimeout(() => {
        setDisplayId(null);
        setDetail(null);
      }, 120);
      return () => window.clearTimeout(t);
    }
  }, [receiptId, displayId]);

  useEffect(() => {
    if (!displayId || !projectId) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setVerifyResult(null);
    void (async () => {
      try {
        const d = await getReceipt(displayId, projectId);
        if (!cancelled) {
          setDetail(d);
        }
      } catch (e) {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : "Failed to load receipt");
          setDetail(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [displayId, projectId]);

  useEffect(() => {
    if (!displayId) {
      return;
    }
    function onKey(ev: KeyboardEvent): void {
      if (ev.key === "Escape") {
        closeAnimated();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [displayId, closeAnimated]);

  useEffect(() => {
    if (displayId) {
      panelRef.current?.focus();
    }
  }, [displayId]);

  if (!displayId) {
    return null;
  }

  const headerCopy = (): void => {
    if (!detail) {
      return;
    }
    void navigator.clipboard.writeText(detail.id);
    toast.success("Copied");
  };

  const onVerify = async (): Promise<void> => {
    if (!displayId || !projectId) {
      return;
    }
    setVerifyPending(true);
    setVerifyResult(null);
    await new Promise((r) => setTimeout(r, 250));
    try {
      const r = await verifyReceipt(displayId, projectId);
      setVerifyResult(r);
      if (r.valid) {
        toast.success("Receipt verified");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Verification failed");
    } finally {
      setVerifyPending(false);
    }
  };

  const httpTint =
    detail && detail.http_status >= 400
      ? "text-status-denied-fg"
      : detail && detail.http_status >= 200 && detail.http_status < 300
        ? "text-status-ok-fg"
        : "text-text-primary";

  return (
    <div
      className="fixed inset-0 z-[70] flex justify-end"
      aria-modal="true"
      role="dialog"
      aria-labelledby={titleId}
    >
      <button
        type="button"
        className={cn(
          "absolute inset-0 bg-[var(--surface-overlay)] transition-opacity duration-base ease-in",
          slideIn ? "opacity-100" : "opacity-0",
        )}
        aria-label="Close drawer"
        onClick={closeAnimated}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={cn(
          "relative flex h-full w-full max-w-[var(--density-drawer)] flex-col border-l border-[var(--border-default)] bg-surface-card shadow-md outline-none transition-transform ease-out",
          slideIn ? "duration-base translate-x-0" : "duration-fast translate-x-full ease-in",
        )}
      >
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-[var(--border-subtle)] px-4 py-4">
          <div className="min-w-0 flex-1">
            <button
              type="button"
              className="block w-full text-left font-mono text-[13px] text-text-primary hover:underline"
              onClick={headerCopy}
              title="Copy full receipt ID"
            >
              <span id={titleId} className="break-all">
                {detail?.id ?? displayId}
              </span>
            </button>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {detail ? <VerdictStatusPill verdict={detail.verdict} /> : null}
            <Button type="button" variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={closeAnimated} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {loading ? (
            <div className="space-y-3 p-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-md bg-surface-elevated" />
              ))}
            </div>
          ) : null}

          {loadError ? (
            <div className="p-4 text-body text-[var(--status-denied-fg)]" role="alert">
              {loadError}
            </div>
          ) : null}

          {!loading && detail ? (
            <div className="pb-8">
              <section className="border-b border-[var(--border-subtle)] px-4 py-4">
                <p className="text-micro text-text-secondary">ACTION</p>
                <p className="mt-2 font-mono text-body text-text-primary">{detail.action_type}</p>
                <p className="mt-1 text-body text-text-primary">
                  {detail.upstream_provider}
                  {detail.upstream_model ? ` · ${detail.upstream_model}` : ""}
                </p>
                <p className="mt-2 font-mono text-mono-caption text-text-tertiary truncate" title={detail.target}>
                  {detail.target}
                </p>
                <div className="mt-3 flex flex-wrap gap-4 text-body tabular-nums">
                  <span>
                    HTTP{" "}
                    <span className={cn("font-medium", httpTint)}>{detail.http_status || "—"}</span>
                  </span>
                  <span className="text-text-secondary">
                    Latency <span className="text-text-primary">{detail.upstream_latency_ms}ms</span>
                  </span>
                </div>
                {detail.token_usage ? (
                  <div className="mt-2 text-body-s text-text-secondary tabular-nums">
                    Tokens: prompt {detail.token_usage.prompt_tokens ?? "—"} · completion{" "}
                    {detail.token_usage.completion_tokens ?? "—"} · total {detail.token_usage.total_tokens ?? "—"}
                  </div>
                ) : null}
              </section>

              <section className="border-b border-[var(--border-subtle)] px-4 py-4">
                <p className="text-micro text-text-secondary">CRYPTOGRAPHIC PROOF</p>
                <CryptoHexRow
                  label="Receipt hash (SHA-256)"
                  standardNote="NIST SHA-256 digest of canonical sealed payload"
                  hex={detail.receipt_hash_hex}
                />
                <CryptoHexRow
                  label="Ed25519 signature"
                  standardNote="NIST FIPS 186-5, classical"
                  hex={detail.ed25519_sig_hex}
                />
                <CryptoHexRow
                  label="ML-DSA-65 signature"
                  standardNote="NIST FIPS 204, NIST PQC Level 3"
                  hex={detail.ml_dsa_sig_hex}
                />
                <CryptoHexRow
                  label="Merkle leaf"
                  standardNote="Leaf preimage anchored in project Merkle tree"
                  hex={detail.merkle_leaf_hex}
                />
                {detail.merkle_root_hex ? (
                  <CryptoHexRow label="Merkle root" standardNote="Tree root at seal time" hex={detail.merkle_root_hex} />
                ) : null}
                <div className="space-y-1.5 py-3">
                  <div className="text-body-s text-text-secondary">Signing key ID</div>
                  <div className="font-mono text-mono-caption text-text-primary">{detail.key_id}</div>
                </div>
                <div className="mt-2 space-y-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={detail.status !== "sealed" || verifyPending}
                    onClick={() => void onVerify()}
                  >
                    {verifyPending ? (
                      <>
                        <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        Verifying…
                      </>
                    ) : (
                      "Verify signatures"
                    )}
                  </Button>
                  {verifyResult ? (
                    <div className="text-body-s">
                      {verifyResult.valid ? (
                        <span className="flex items-center gap-2 text-status-ok-fg">
                          <Check className="h-4 w-4 shrink-0" />
                          All signatures valid
                        </span>
                      ) : (
                        <div className="space-y-1 text-[var(--status-denied-fg)]">
                          <span className="flex items-center gap-2">
                            <XCircle className="h-4 w-4 shrink-0" />
                            Verification failed
                          </span>
                          <ul className="list-inside list-disc pl-1 text-text-secondary">
                            <li>Ed25519: {verifyResult.ed25519_valid ? "valid" : "invalid"}</li>
                            <li>ML-DSA-65: {verifyResult.ml_dsa_valid ? "valid" : "invalid"}</li>
                            <li>Merkle proof: {verifyResult.merkle_valid ? "valid" : "invalid"}</li>
                            {verifyResult.errors.map((err) => (
                              <li key={err} className="text-[var(--status-denied-fg)]">
                                {err}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              </section>

              <section className="border-b border-[var(--border-subtle)] px-4 py-4">
                <p className="text-micro text-text-secondary">REQUEST/RESPONSE HASHES</p>
                <CryptoHexRow
                  label="Request hash"
                  standardNote="SHA-256 of canonical request body observed by gateway"
                  hex={detail.request_hash_hex}
                />
                <CryptoHexRow
                  label="Response hash"
                  standardNote="SHA-256 of upstream response body observed by gateway"
                  hex={detail.response_hash_hex}
                />
              </section>

              {detail.approval_status ? (
                <section className="border-b border-[var(--border-subtle)] px-4 py-4">
                  <p className="text-micro text-text-secondary">APPROVAL</p>
                  <p className="mt-2 text-body text-text-primary">{detail.approval_status}</p>
                  {detail.approved_by_email ? (
                    <p className="mt-1 text-body-s text-text-secondary">Approver: {detail.approved_by_email}</p>
                  ) : null}
                  {detail.approved_at ? (
                    <p className="mt-1 font-mono text-mono-caption text-text-tertiary tabular-nums">{detail.approved_at}</p>
                  ) : null}
                  {detail.approval_reason ? (
                    <p className="mt-2 text-body-s text-text-secondary">{detail.approval_reason}</p>
                  ) : null}
                </section>
              ) : null}

              <section className="px-4 py-4">
                <p className="text-micro text-text-secondary">TIMESTAMPS</p>
                <dl className="mt-2 space-y-2 font-mono text-mono-caption text-text-tertiary tabular-nums">
                  <div>
                    <dt className="text-text-secondary">Intent created</dt>
                    <dd className="text-text-primary" title={formatRelative(detail.intent_created_at)}>
                      {detail.intent_created_at}
                    </dd>
                  </div>
                  {detail.executed_at_label ? (
                    <div>
                      <dt className="text-text-secondary">Executed</dt>
                      <dd className="text-text-primary">{detail.executed_at_label}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt className="text-text-secondary">Sealed</dt>
                    <dd className="text-text-primary" title={detail.sealed_at ? formatRelative(detail.sealed_at) : undefined}>
                      {detail.sealed_at ?? "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-text-secondary">Relative</dt>
                    <dd className="text-text-primary">{formatRelative(detail.sealed_at)}</dd>
                  </div>
                </dl>
              </section>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
