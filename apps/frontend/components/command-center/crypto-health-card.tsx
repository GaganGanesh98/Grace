"use client";

import { Check } from "lucide-react";
import { type ReactElement } from "react";

import { AggregateErrorBody } from "@/components/command-center/aggregate-error-body";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { CryptoSigningStatus, MerkleStatus } from "@/lib/command-center-types";
import { CommandCenterRequestError } from "@/lib/command-center-api";
import { useCryptoHealthQuery } from "@/lib/queries/command-center";

const GREEN = "#6db862";
const AMBER = "#d4a030";
const RED = "#e05050";

type CryptoHealthCardProps = { projectId: string | null };

function Dot({ color }: { color: string }): ReactElement {
  return <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />;
}

const KNOWN: Record<string, true> = {
  all_signed: true,
  partial: true,
  never_signed: true,
  no_data: true,
};

function resolveSigningStatus(raw: string): CryptoSigningStatus {
  if (raw in KNOWN) {
    return raw as CryptoSigningStatus;
  }
  return "never_signed";
}

function signingDisplay(
  status: string,
): { check: "yes" | "amber" | "red" | "muted"; text: string; textColor: string } {
  const s = resolveSigningStatus(status);
  if (s === "all_signed") {
    return { check: "yes", text: "all signed", textColor: "var(--axiom-success)" };
  }
  if (s === "partial") {
    return { check: "amber", text: "partial", textColor: AMBER };
  }
  if (s === "no_data") {
    return { check: "muted", text: "no sealed receipts yet", textColor: "var(--axiom-text-dim)" };
  }
  return { check: "red", text: "no signatures yet", textColor: RED };
}

function SigningRow({ label, status }: { label: string; status: CryptoSigningStatus }): ReactElement {
  const d = signingDisplay(status);
  return (
    <div className="flex items-center justify-between gap-2 text-axiom-14">
      <span className="text-[var(--axiom-text-muted)]">{label}</span>
      <span className="inline-flex items-center gap-1.5">
        {d.check === "yes" ? (
          <Check className="h-3.5 w-3.5 shrink-0" strokeWidth={2.5} style={{ color: GREEN }} aria-hidden />
        ) : d.check === "amber" ? (
          <Dot color={AMBER} />
        ) : d.check === "red" ? (
          <Dot color={RED} />
        ) : (
          <span className="text-[var(--axiom-text-dim)]" aria-hidden>
            —
          </span>
        )}
        <span className="font-mono" style={{ color: d.textColor }}>
          {d.text}
        </span>
      </span>
    </div>
  );
}

function MerkleRow({ status }: { status: MerkleStatus }): ReactElement {
  if (status === "healthy") {
    return (
      <div className="flex items-center justify-between gap-2 text-axiom-14">
        <span className="text-[var(--axiom-text-muted)]">Merkle</span>
        <span className="inline-flex items-center gap-1.5">
          <Check className="h-3.5 w-3.5 shrink-0" strokeWidth={2.5} style={{ color: GREEN }} aria-hidden />
          <span className="font-mono" style={{ color: "var(--axiom-success)" }}>
            healthy
          </span>
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center justify-between gap-2 text-axiom-14">
      <span className="text-[var(--axiom-text-muted)]">Merkle</span>
      <span className="inline-flex items-center gap-1.5 font-mono text-[var(--axiom-text-dim)]">
        <span>—</span> no entries yet
      </span>
    </div>
  );
}

export function CryptoHealthCard({ projectId }: CryptoHealthCardProps): ReactElement {
  const { data, isPending, isError, error, refetch } = useCryptoHealthQuery({ projectId });
  const isForbidden = error instanceof CommandCenterRequestError && error.status === 403;

  if (isError && !isPending) {
    return (
      <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
        <CardHeader>
          <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Cryptographic health</h2>
        </CardHeader>
        <CardContent>
          <AggregateErrorBody error={error} isForbidden={isForbidden} onRetry={() => void refetch()} />
        </CardContent>
      </Card>
    );
  }

  if (isPending) {
    return (
      <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
        <CardHeader>
          <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Cryptographic health</h2>
        </CardHeader>
        <CardContent className="space-y-3">
          {["a", "b", "c"].map((k) => (
            <div key={k} className="flex justify-between gap-2">
              <Skeleton className="h-4 w-1/3 max-w-24" />
              <Skeleton className="h-4 w-1/3 max-w-20" />
            </div>
          ))}
          <div className="border-t border-[var(--axiom-border)] pt-3" />
          <Skeleton className="h-3 w-4/5 max-w-xs" />
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
        <CardHeader>
          <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Cryptographic health</h2>
        </CardHeader>
        <CardContent>
          <p className="text-axiom-15 text-[var(--axiom-text-muted)]">No data</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] text-[var(--axiom-text)] ring-[var(--axiom-border)]">
      <CardHeader>
        <h2 className="text-axiom-16 font-medium text-[var(--axiom-text)]">Cryptographic health</h2>
      </CardHeader>
      <CardContent className="space-y-3">
        <SigningRow label="Ed25519" status={data.ed25519_status} />
        <SigningRow label="ML-DSA-65" status={data.mldsa65_status} />
        <MerkleRow status={data.merkle_status} />

        <div className="border-t border-[var(--axiom-border)] pt-3" />
        <p className="text-axiom-13 text-[var(--axiom-text-muted)]">
          Next rotation:{" "}
          <span className="font-mono">
            {data.next_rotation_days == null
              ? "not configured"
              : `${data.next_rotation_days} days`}
          </span>
        </p>
      </CardContent>
    </Card>
  );
}
