"use client";

import { useQuery } from "@tanstack/react-query";
import { type ReactElement } from "react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { fetchActiveGovernancePolicy } from "@/lib/governance-api";
import { usePolicyBreakdownQuery } from "@/lib/queries/command-center";

type PolicyCardProps = { projectId: string | null };

export function PolicyCard({ projectId }: PolicyCardProps): ReactElement {
  const q = useQuery({
    queryKey: projectId ? dashboardKeys.activePolicy(projectId) : ["axiom", "active-policy", "none"],
    queryFn: () => fetchActiveGovernancePolicy(projectId!),
    enabled: Boolean(projectId),
  });

  const br = usePolicyBreakdownQuery({ projectId });
  const breakdown = br.data;

  if (!projectId) {
    return (
      <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
        <CardHeader>
          <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Active policy</h2>
        </CardHeader>
        <CardContent>
          <p className="text-axiom-15 text-[var(--axiom-text-muted)]">Select a project to view policy</p>
        </CardContent>
      </Card>
    );
  }

  if (q.isError) {
    return (
      <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
        <CardHeader>
          <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Active policy</h2>
        </CardHeader>
        <CardContent>
          <p className="text-axiom-15 text-[var(--axiom-text-muted)]">No active policy configured</p>
        </CardContent>
      </Card>
    );
  }

  const name = q.data ? (q.data.display_name || q.data.name) : null;
  const showEmptyPolicyName = name == null;

  return (
    <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
      <CardHeader>
        <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Active policy</h2>
        {showEmptyPolicyName && !q.isPending ? (
          <p className="text-axiom-15 text-[var(--axiom-text-muted)]">No active policy configured</p>
        ) : (
          <p
            className="text-axiom-15 font-medium text-[var(--axiom-text)]"
            data-testid="policy-name"
          >
            {q.isPending ? "…" : (name ?? "—")}
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-2.5 text-axiom-14 text-[var(--axiom-text-muted)]">
        {br.isPending ? (
          <>
            <div className="flex justify-between gap-2">
              <span>Evaluated</span>
              <Skeleton className="h-3 w-10" />
            </div>
            <div className="flex justify-between gap-2">
              <span>Allowed</span>
              <Skeleton className="h-3 w-8" />
            </div>
            <div className="flex justify-between gap-2">
              <div className="inline-flex items-center gap-1">
                <span>Escalated</span>
                <span className="h-2 w-8 opacity-0" />
              </div>
              <Skeleton className="h-3 w-8" />
            </div>
          </>
        ) : (
          <>
            <div className="flex justify-between gap-2">
              <span>Evaluated</span>
              <span className="font-mono">{breakdown ? breakdown.evaluated_count : "—"}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span>Allowed</span>
              <span className="font-mono">{breakdown ? breakdown.approved_count : "—"}</span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
              <span className="inline-flex flex-wrap items-center gap-1.5">
                <span>Escalated</span>
                {breakdown && breakdown.denied_count > 0 ? (
                  <span className="text-axiom-12 text-[#e05050]">
                    {breakdown.denied_count} denied
                  </span>
                ) : null}
              </span>
              <span className="font-mono">{breakdown ? breakdown.escalated_count : "—"}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
