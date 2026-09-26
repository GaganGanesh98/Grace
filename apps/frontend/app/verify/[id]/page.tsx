"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type ReactElement } from "react";

import { GovernancePipeline } from "@/components/governance-pipeline";
import { SignatureCheck } from "@/components/signature-check";
import { fetchPublicReceipt } from "@/lib/governance-api";
import { formatRecordId } from "@/lib/governance-display";
import type { GovernanceReceiptRecord } from "@/lib/governance-types";

function Wordmark(): ReactElement {
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="flex items-center gap-2.5">
        <div className="flex h-[22px] w-[22px] shrink-0 items-center justify-center">
          <div className="flex h-[22px] w-[22px] rotate-45 items-center justify-center border border-text-primary bg-transparent">
            <div className="h-1.5 w-1.5 -rotate-45 bg-text-primary" />
          </div>
        </div>
        <span className="font-mono text-[13px] font-medium uppercase tracking-[3px] text-text-primary">
          Grace
        </span>
      </div>
    </div>
  );
}

function PublicVerifyInner(): ReactElement {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const id = params.id;
  const token = search.get("token") ?? search.get("share_token");
  const [receipt, setReceipt] = useState<GovernanceReceiptRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function run(): Promise<void> {
      if (!token) {
        setError("Missing share token. Append ?token=… to this URL (matches intent metadata).");
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const r = await fetchPublicReceipt(id, token);
        if (!cancelled) {
          setReceipt(r);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not load attestation");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [id, token]);

  const sealed = receipt?.status === "sealed";
  const hasEd = Boolean(receipt?.signatures?.ed25519);
  const hasMl = Boolean(receipt?.signatures?.ml_dsa_65);
  const hasMerkle =
    Boolean(receipt?.merkle?.root) &&
    Array.isArray(receipt?.merkle?.path) &&
    (receipt?.merkle?.path?.length ?? 0) > 0;

  return (
    <div className="min-h-screen bg-[var(--background)] px-4 py-12 text-text-primary">
      <div className="mx-auto max-w-3xl">
        <Wordmark />
        <h1 className="mt-10 text-center font-[family-name:var(--font-sans)] text-[24px] font-medium">
          Public attestation
        </h1>
        <p className="mx-auto mt-2 max-w-xl text-center text-[15px] text-text-secondary">
          Read-only view. Cryptographic verification by receipt ID requires an authenticated project API key on
          the backend; this page loads via share token only.
        </p>

        {loading ? (
          <div className="mt-12 h-40 animate-pulse rounded-lg bg-[var(--surface-muted)]" />
        ) : null}

        {error ? (
          <div className="mt-10 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-[15px] text-status-denied-fg">
            {error}
          </div>
        ) : null}

        {receipt ? (
          <>
            <div className="mt-10 grid gap-4 md:grid-cols-3">
              <SignatureCheck label="Ed25519" ok={sealed && hasEd} />
              <SignatureCheck label="ML-DSA-65" ok={sealed && hasMl} />
              <div className="rounded-lg border border-border bg-[var(--surface-muted)] px-4 py-3">
                <div className="font-mono text-[13px] uppercase tracking-wide text-text-secondary">
                  Merkle proof
                </div>
                <div
                  className={`mt-1 font-mono text-[15px] ${sealed && hasMerkle ? "text-status-ok-fg" : "text-status-denied-fg"}`}
                >
                  {sealed && hasMerkle ? "✓ anchored" : "✗ incomplete"}
                </div>
              </div>
            </div>

            <div className="mt-10 rounded-lg border border-border bg-[var(--surface-muted)] p-6">
              <div className="mb-6 font-mono text-[13px] text-text-secondary">
                Record {formatRecordId(receipt.id)}
              </div>
              <GovernancePipeline receipt={receipt} />
            </div>
          </>
        ) : null}

        <footer className="mt-16 text-center font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
          Verified by Grace — post-quantum cryptographic governance
        </footer>
      </div>
    </div>
  );
}

export default function PublicVerifyPage(): ReactElement {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[var(--background)] font-mono text-[13px] text-text-tertiary">
          Loading attestation…
        </div>
      }
    >
      <PublicVerifyInner />
    </Suspense>
  );
}
