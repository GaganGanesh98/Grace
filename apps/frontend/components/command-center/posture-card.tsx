"use client";

import { type ReactElement } from "react";

import { AggregateErrorBody } from "@/components/command-center/aggregate-error-body";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CommandCenterRequestError } from "@/lib/command-center-api";
import { usePostureQuery } from "@/lib/queries/command-center";

type PostureCardProps = { projectId: string | null };

// The ring is a graphical mark (3:1 against the card); the percentage is text
// and needs the -strong variant (4.5:1). See scripts/check-contrast.py.
function postureTone(violations: number): "success" | "warning" | "danger" {
  if (violations === 0) {
    return "success";
  }
  if (violations < 5) {
    return "warning";
  }
  return "danger";
}

function postureDisplayPercent(calls: number, violations: number): number {
  if (violations === 0) {
    return 100;
  }
  if (calls === 0) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(((calls - violations) / calls) * 100)));
}

export function PostureCard({ projectId }: PostureCardProps): ReactElement {
  const { data, isPending, isError, error, refetch } = usePostureQuery({ projectId });

  const isForbidden = error instanceof CommandCenterRequestError && error.status === 403;

  const body = (): ReactElement => {
    if (isError && !isPending) {
      return <AggregateErrorBody error={error} isForbidden={isForbidden} onRetry={() => void refetch()} />;
    }
    if (isPending) {
      return (
        <div className="space-y-3">
          <div className="mx-auto h-20 w-20 max-w-full">
            <Skeleton className="h-full w-full rounded-full" />
          </div>
          <Skeleton className="mx-auto h-3 w-2/3 max-w-xs" />
          <Skeleton className="mx-auto h-3 w-1/2 max-w-xs" />
        </div>
      );
    }
    if (!data) {
      return <p className="text-axiom-15 text-[var(--axiom-text-muted)]">No data</p>;
    }
    if (data.calls_governed === 0) {
      return (
        <p className="text-center text-axiom-15 text-[var(--axiom-text-muted)]">No activity yet</p>
      );
    }

    const { violations, calls_governed: cg } = data;
    const pct = postureDisplayPercent(cg, violations);
    const tone = postureTone(violations);
    const arcColor = `var(--${tone})`;
    const fillDeg = (pct / 100) * 360;
    return (
      <>
        <div className="flex items-center justify-center">
          <div
            className="relative h-20 w-20 rounded-full"
            style={{
              background: `conic-gradient(from 180deg, ${arcColor} 0deg ${fillDeg}deg, var(--axiom-border) ${fillDeg}deg 360deg)`,
            }}
            aria-hidden
          >
            <div className="absolute inset-2.5 flex items-center justify-center rounded-full bg-[var(--axiom-bg-card)]">
              <span
                className="text-axiom-18 font-mono"
                style={{ color: `var(--${tone}-strong)` }}
              >{`${pct}%`}</span>
            </div>
          </div>
        </div>
        <p className="text-center text-axiom-14 text-[var(--axiom-text-muted)]">
          {data.calls_governed} calls · {data.runs_completed} runs · {data.violations} violations
        </p>
      </>
    );
  };

  return (
    <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
      <CardHeader>
        <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Governance posture</h2>
      </CardHeader>
      <CardContent className="min-h-40 space-y-3">{body()}</CardContent>
    </Card>
  );
}
