import type { ReactElement } from "react";

import { CodeBlock } from "@/components/code-block";
import { PipelineStage } from "@/components/pipeline-stage";
import { VerdictBadge } from "@/components/verdict-badge";
import { VerificationBadge } from "@/components/verification-badge";
import { formatRecordId, toUiVerdict, toUiVerification } from "@/lib/governance-display";
import type { GovernanceReceiptRecord } from "@/lib/governance-types";

function Kv({
  k,
  v,
}: {
  k: string;
  v: string | number | boolean | null | undefined;
}): ReactElement {
  return (
    <div className="grid grid-cols-[minmax(0,180px)_1fr] gap-x-4 gap-y-1 border-b border-[rgba(255,255,255,0.04)] py-2 last:border-0">
      <div className="font-mono text-axiom-13 text-[#6B7490]">{k}</div>
      <div className="break-all font-mono text-axiom-13 text-[#A0A8BC]">{String(v ?? "—")}</div>
    </div>
  );
}

export function GovernancePipeline({ receipt }: { receipt: GovernanceReceiptRecord }): ReactElement {
  const intent = receipt.intent;
  const verdict = receipt.verdict;
  const ctx = verdict.context ?? {};
  const rules = Array.isArray(verdict.rules_evaluated) ? verdict.rules_evaluated : [];
  const uiV = toUiVerdict(verdict.verdict);
  const uiVer = toUiVerification(receipt.verification?.status ?? "", receipt.status === "sealed");

  return (
    <div className="space-y-0">
      <PipelineStage index={1} title="Declaration of intent">
        <div className="space-y-0">
          <Kv k="agent_id" v={intent.agent_id} />
          <Kv k="action_type" v={intent.action_type} />
          <Kv k="target" v={intent.target} />
          <Kv k="risk" v={intent.risk_declared} />
          <Kv k="parameters" v={JSON.stringify(intent.parameters ?? {})} />
        </div>
      </PipelineStage>

      <PipelineStage index={2} title="Risk context assessment">
        <div className="space-y-0">
          {Object.keys(ctx).length === 0 ? (
            <p className="text-axiom-15 text-[#A0A8BC]">No additional context attached.</p>
          ) : (
            Object.entries(ctx).map(([key, val]) => (
              <Kv key={key} k={key} v={typeof val === "object" ? JSON.stringify(val) : String(val)} />
            ))
          )}
        </div>
      </PipelineStage>

      <PipelineStage index={3} title="Policy evaluation">
        <div className="space-y-3">
          <Kv k="policy_version" v={verdict.policy_version} />
          <div className="font-mono text-axiom-13 uppercase tracking-wide text-[#A0A8BC]">Rules checked</div>
          <ul className="space-y-2">
            {rules.length === 0 ? (
              <li className="font-mono text-axiom-13 text-[#6B7490]">—</li>
            ) : (
              rules.map((r, i) => {
                const rule = r as Record<string, unknown>;
                const matched = Boolean(rule.matched ?? rule.match);
                return (
                  <li
                    key={i}
                    className={
                      matched
                        ? "rounded border border-border-strong bg-surface-elevated px-3 py-2 font-mono text-axiom-13 text-[#F0F2F8]"
                        : "rounded border border-[rgba(255,255,255,0.06)] px-3 py-2 font-mono text-axiom-13 text-[#A0A8BC]"
                    }
                  >
                    {JSON.stringify(r)}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      </PipelineStage>

      <PipelineStage index={4} title="Authorization decision">
        <div className="flex flex-wrap items-center gap-4">
          <VerdictBadge verdict={uiV} />
          {verdict.reason ? (
            <p className="max-w-xl text-axiom-15 text-[#F0F2F8]">{verdict.reason}</p>
          ) : null}
        </div>
      </PipelineStage>

      <PipelineStage index={5} title="Execution evidence">
        {receipt.execution && Object.keys(receipt.execution).length > 0 ? (
          <CodeBlock>{JSON.stringify(receipt.execution, null, 2)}</CodeBlock>
        ) : (
          <p className="text-axiom-15 text-[#A0A8BC]">No execution payload recorded yet.</p>
        )}
      </PipelineStage>

      <PipelineStage index={6} title="Compliance verification">
        <div className="space-y-3">
          <VerificationBadge status={uiVer} />
          {Array.isArray(receipt.verification?.mismatches) && receipt.verification.mismatches.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 font-mono text-axiom-13 text-[#F87171]">
              {receipt.verification.mismatches.map((m, i) => (
                <li key={i}>{JSON.stringify(m)}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </PipelineStage>

      <PipelineStage index={7} title="Cryptographic attestation" showConnector={false}>
        <div className="space-y-3">
          <Kv k="record_id" v={formatRecordId(receipt.id)} />
          <Kv
            k="ed25519"
            v={receipt.signatures?.ed25519 ? "present (base64)" : "missing"}
          />
          <Kv
            k="ml_dsa_65"
            v={receipt.signatures?.ml_dsa_65 ? "present (base64)" : "missing"}
          />
          <Kv k="merkle_depth" v={receipt.merkle?.depth ?? "—"} />
          <Kv k="leaf_hash" v={receipt.merkle?.leaf || "—"} />
          <Kv k="root_hash" v={receipt.merkle?.root || "—"} />
        </div>
      </PipelineStage>
    </div>
  );
}
