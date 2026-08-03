"use client";

import { useQuery } from "@tanstack/react-query";
import { type ReactElement } from "react";

import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { fetchActiveGovernancePolicy } from "@/lib/governance-api";

const TEMPLATES = [
  {
    name: "Starter safe",
    summary: "Low risk auto-allowed, high risk held for review",
    rules: [
      "deny-critical — risk = critical → DENY",
      "hold-high — risk = high → HOLD",
      "allow-medium — risk = medium → ALLOW",
      "allow-low — risk = low → ALLOW",
    ],
  },
  {
    name: "Approval first",
    summary: "All actions require human approval",
    rules: ["default — any intent → HOLD"],
  },
  {
    name: "Read only",
    summary: "Everything allowed, full audit trail",
    rules: ["permit-all — any intent → ALLOW"],
  },
] as const;

export default function PoliciesPage(): ReactElement {
  const { activeProjectId } = useProjectWorkspace();

  const policyQuery = useQuery({
    queryKey: activeProjectId ? dashboardKeys.activePolicy(activeProjectId) : ["axiom", "active-policy", "none"],
    queryFn: () => fetchActiveGovernancePolicy(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });

  const policy = policyQuery.data;

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-axiom-24 font-medium text-[#F0F2F8]">Policies</h1>
        <p className="mt-2 max-w-2xl text-axiom-15 text-[#A0A8BC]">
          Active governance policy is read from project configuration (YAML templates). Templates below describe common
          bundles.
        </p>
      </header>

      <section className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0A0A14] p-6">
        {policyQuery.isPending ? (
          <div className="h-24 animate-pulse rounded bg-[#0A0A14]" />
        ) : policyQuery.isError ? (
          <p className="font-mono text-axiom-14 text-[#F87171]">
            {policyQuery.error instanceof Error ? policyQuery.error.message : "Could not load policy"}
          </p>
        ) : policy ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-axiom-22 font-medium text-[#F0F2F8]">{policy.display_name}</h2>
                <p className="mt-1 font-mono text-axiom-13 text-[#A0A8BC]">
                  <span className="text-[#6B7490]">Key</span>{" "}
                  <span className="text-[#F0F2F8]">{policy.name}</span>
                  <span className="mx-2 text-[#6B7490]">·</span>
                  <span className="text-[#6B7490]">Version</span>{" "}
                  <span className="text-[#F0F2F8]">{policy.version}</span>
                </p>
                {policy.is_default_configuration ? (
                  <p className="mt-3 font-mono text-axiom-12 text-[#6B7490]">
                    Default policy — no custom policy configured in project settings.
                  </p>
                ) : null}
              </div>
              <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 font-mono text-axiom-12 uppercase tracking-wide text-[#34D399]">
                Active
              </span>
            </div>
            <ol className="mt-6 space-y-2 font-mono text-axiom-14 text-[#F0F2F8]">
              {policy.rules.length === 0 ? (
                <li className="text-[#6B7490]">No rules in YAML (unexpected).</li>
              ) : (
                policy.rules.map((r, i) => {
                  const name = typeof r.name === "string" ? r.name : "";
                  const cond = typeof r.condition === "string" ? r.condition : "";
                  const verdict = typeof r.verdict === "string" ? r.verdict : "";
                  const line =
                    name && cond && verdict
                      ? `${name} — ${cond} → ${verdict.toUpperCase()}`
                      : JSON.stringify(r);
                  return (
                    <li key={`${name}-${i}`}>
                      {i + 1}. {line}
                    </li>
                  );
                })
              )}
            </ol>
          </>
        ) : null}
      </section>

      <section>
        <h2 className="mb-4 font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
          Available templates
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {TEMPLATES.map((t) => (
            <div
              key={t.name}
              className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0A0A14] p-5"
            >
              <h3 className="text-axiom-18 font-medium text-[#F0F2F8]">{t.name}</h3>
              <p className="mt-2 text-axiom-14 text-[#A0A8BC]">{t.summary}</p>
              <ul className="mt-4 space-y-1 font-mono text-axiom-13 text-[#6B7490]">
                {t.rules.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
