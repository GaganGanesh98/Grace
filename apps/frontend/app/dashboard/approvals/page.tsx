"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactElement, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { approveReceipt, fetchPendingReceipts, rejectReceipt } from "@/lib/governance-api";
import { cn } from "@/lib/utils";

function formatRemaining(seconds: number): string {
  if (seconds <= 0) {
    return "expired";
  }
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m left`;
  }
  if (m > 0) {
    return `${m}m ${s}s left`;
  }
  return `${s}s left`;
}

/**
 * Human approvals (Phase 6.5) — target for Command Center "REVIEW →" and pending flows.
 * Uses the same BFF + approve/deny as the pre–7.5.2 command center.
 */
export default function ApprovalsPage(): ReactElement {
  const { activeProjectId } = useProjectWorkspace();
  const queryClient = useQueryClient();
  const [processing, setProcessing] = useState<{ id: string; kind: "approve" | "reject" } | null>(null);

  const pendingQuery = useQuery({
    queryKey: activeProjectId ? dashboardKeys.pendingReceipts(activeProjectId) : ["axiom", "pending", "none"],
    queryFn: () => fetchPendingReceipts(activeProjectId!),
    enabled: Boolean(activeProjectId),
    refetchInterval: 10_000,
  });

  const list = pendingQuery.data ?? [];
  const loading = Boolean(activeProjectId) && pendingQuery.isPending;
  const error =
    pendingQuery.error instanceof Error
      ? pendingQuery.error.message
      : pendingQuery.error
        ? "Failed to load pending approvals"
        : null;

  const refresh = async (): Promise<void> => {
    if (!activeProjectId) {
      return;
    }
    await queryClient.invalidateQueries({ queryKey: dashboardKeys.pendingReceipts(activeProjectId) });
    await queryClient.invalidateQueries({ queryKey: dashboardKeys.ledgerBundle(activeProjectId) });
  };

  async function handleApprove(receiptId: string): Promise<void> {
    if (processing) {
      return;
    }
    setProcessing({ id: receiptId, kind: "approve" });
    try {
      await approveReceipt(receiptId);
      toast.success("Action approved");
      await refresh();
    } catch (err: unknown) {
      toast.error(`Approval failed: ${err instanceof Error ? err.message : "error"}`);
    } finally {
      setProcessing(null);
    }
  }

  async function handleReject(receiptId: string): Promise<void> {
    if (processing) {
      return;
    }
    setProcessing({ id: receiptId, kind: "reject" });
    try {
      await rejectReceipt(receiptId);
      toast.success("Action rejected");
      await refresh();
    } catch (err: unknown) {
      toast.error(`Rejection failed: ${err instanceof Error ? err.message : "error"}`);
    } finally {
      setProcessing(null);
    }
  }

  if (!activeProjectId) {
    return (
      <div className="space-y-6">
        <h1 className="text-axiom-24 font-medium text-[var(--axiom-text)]">Approvals</h1>
        <p className="text-axiom-15 text-[var(--axiom-text-muted)]">Select a project in the sidebar to load pending items.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-axiom-24 font-medium text-[var(--axiom-text)]">Pending approvals</h1>
        <p className="mt-2 max-w-2xl text-axiom-15 text-[var(--axiom-text-muted)]">
          Holds awaiting human review. This page preserves the Phase 6.5 flow (approve and reject against the
          same endpoints as before).
        </p>
      </header>

      {error ? (
        <div
          className="rounded-lg border border-[var(--axiom-danger)]/30 bg-[rgba(224,80,80,0.08)] px-4 py-3 text-axiom-15 text-[var(--axiom-danger)]"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      {loading ? (
        <div
          className="h-40 rounded-md border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] animate-pulse"
          role="status"
          aria-label="Loading"
        />
      ) : null}

      {!loading && !error && list.length === 0 ? (
        <p className="text-axiom-15 text-[var(--axiom-text-muted)]">No pending holds — you&apos;re all caught up.</p>
      ) : null}

      <ul className="space-y-3">
        {list.map((r) => (
          <li
            key={r.receipt_id}
            className="space-y-3 rounded-md border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] p-4"
          >
            <div className="font-mono text-axiom-12 text-[var(--axiom-text)]">{r.agent_id}</div>
            <div className="text-axiom-13 text-[var(--axiom-text-muted)]">
              {r.action_type} → {r.target}
            </div>
            {r.reason ? (
              <p className="text-axiom-12 text-[var(--axiom-text-label)]">Hold: {r.reason}</p>
            ) : null}
            <p className="text-axiom-12 text-[var(--axiom-warn)]">{formatRemaining(r.time_remaining_seconds)}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                disabled={Boolean(processing)}
                className={cn(
                  "border border-[rgba(109,184,98,0.35)] bg-[rgba(109,184,98,0.12)] text-axiom-12 text-[var(--axiom-success)] hover:bg-[rgba(109,184,98,0.18)]",
                )}
                onClick={() => void handleApprove(r.receipt_id)}
              >
                {processing?.id === r.receipt_id && processing.kind === "approve" ? "APPROVING…" : "APPROVE"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="danger"
                disabled={Boolean(processing)}
                onClick={() => void handleReject(r.receipt_id)}
              >
                {processing?.id === r.receipt_id && processing.kind === "reject" ? "REJECTING…" : "REJECT"}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
