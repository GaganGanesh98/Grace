"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/code-block";
import { GovernancePipeline } from "@/components/governance-pipeline";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { VerdictBadge } from "@/components/verdict-badge";
import { VerificationBadge } from "@/components/verification-badge";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { fetchReceipt, verifyReceiptById } from "@/lib/governance-api";
import type { GovernanceLedgerBundle } from "@/lib/governance-ledger-bundle";
import { formatRecordId, toUiVerdict, toUiVerification } from "@/lib/governance-display";
import type { GovernanceEngineVerifyResponse, GovernanceReceiptRecord } from "@/lib/governance-types";

export default function LedgerDetailPage(): ReactElement {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { activeProjectId } = useProjectWorkspace();
  const id = params.id;
  const [verifyResult, setVerifyResult] = useState<GovernanceEngineVerifyResponse | null>(null);
  const [verifyPending, setVerifyPending] = useState(false);

  const receiptQuery = useQuery({
    queryKey:
      id && activeProjectId ? dashboardKeys.receipt(id, activeProjectId) : ["axiom", "governance-receipt", "disabled"],
    queryFn: async (): Promise<GovernanceReceiptRecord> => {
      if (!activeProjectId) {
        throw new Error("No active project");
      }
      const bundle = queryClient.getQueryData<GovernanceLedgerBundle>(
        dashboardKeys.ledgerBundle(activeProjectId),
      );
      const cached = bundle?.receipts.get(id);
      if (cached) {
        return cached;
      }
      return fetchReceipt(id, undefined, activeProjectId);
    },
    enabled: Boolean(id && activeProjectId),
  });

  const receipt = receiptQuery.data ?? null;
  const loading = receiptQuery.isPending;
  const error =
    receiptQuery.error instanceof Error ? receiptQuery.error.message : receiptQuery.error ? "Failed to load record" : null;

  async function onVerify(): Promise<void> {
    setVerifyPending(true);
    setVerifyResult(null);
    try {
      const r = await verifyReceiptById(id, activeProjectId ?? undefined);
      setVerifyResult(r);
      if (activeProjectId) {
        await queryClient.invalidateQueries({ queryKey: dashboardKeys.receipt(id, activeProjectId) });
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Verify failed");
    } finally {
      setVerifyPending(false);
    }
  }

  async function copyPublicUrl(): Promise<void> {
    const url = `${window.location.origin}/verify/${id}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Public URL copied");
    } catch {
      toast.error("Could not copy");
    }
  }

  if (!activeProjectId) {
    return (
      <div className="space-y-4">
        <p className="text-axiom-15 text-[#A0A8BC]">Select a project to view this record.</p>
        <Button type="button" variant="secondary" onClick={() => router.push("/dashboard/projects")}>
          Projects
        </Button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-2/3 max-w-md animate-pulse rounded bg-[#0A0A14]" />
        <div className="h-96 animate-pulse rounded-lg bg-[#0A0A14]" />
      </div>
    );
  }

  if (error || !receipt) {
    return (
      <div className="space-y-4">
        <p className="text-axiom-15 text-[#F87171]">{error ?? "Record not found"}</p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={() => void receiptQuery.refetch()}>
            Retry
          </Button>
          <Button type="button" variant="secondary" onClick={() => router.push("/dashboard/ledger")}>
            Back to ledger
          </Button>
        </div>
      </div>
    );
  }

  const uiV = toUiVerdict(receipt.verdict.verdict);
  const uiVer = toUiVerification(receipt.verification?.status ?? "", receipt.status === "sealed");

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 border-b border-border-subtle pb-6 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <button
            type="button"
            className="mb-3 rounded-sm border border-transparent bg-transparent px-2 py-1 font-mono text-axiom-13 text-[#A0A8BC] hover:border-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--axiom-electric)] hover:underline"
            onClick={() => router.push("/dashboard/ledger")}
          >
            ← Back to ledger
          </button>
          <h1 className="font-mono text-axiom-20 font-medium text-[#F0F2F8]">{formatRecordId(receipt.id)}</h1>
          <p className="mt-2 font-mono text-axiom-14 text-[#A0A8BC]">{receipt.intent.agent_id}</p>
          <p className="mt-1 font-mono text-axiom-13 text-[#6B7490]">
            {new Date(receipt.intent.created_at).toLocaleString()}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <VerdictBadge verdict={uiV} />
            <VerificationBadge status={uiVer} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={verifyPending || receipt.status !== "sealed"}
            title={receipt.status !== "sealed" ? "Seal required before integrity check" : undefined}
            onClick={() => void onVerify()}
          >
            {verifyPending ? "VALIDATING…" : "VALIDATE INTEGRITY"}
          </Button>
          <Button type="button" variant="secondary" onClick={() => void copyPublicUrl()}>
            PUBLIC ATTESTATION
          </Button>
        </div>
      </div>

      {verifyResult ? (
        <div className="rounded-md border border-border-subtle bg-[#0A0A14] p-4">
          <div className="mb-2 font-mono text-axiom-13 uppercase tracking-wide text-[#A0A8BC]">
            Verify result
          </div>
          <CodeBlock>{JSON.stringify(verifyResult, null, 2)}</CodeBlock>
        </div>
      ) : null}

      <section>
        <h2 className="mb-6 font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
          Governance pipeline
        </h2>
        <GovernancePipeline receipt={receipt} />
      </section>

      <p className="font-mono text-axiom-12 text-[#6B7490]">
        Public viewers need a share token:{" "}
        <Link className="text-[var(--axiom-electric)] hover:underline" href={`/verify/${id}`}>
          {`/verify/${id}`}
        </Link>
      </p>
    </div>
  );
}
