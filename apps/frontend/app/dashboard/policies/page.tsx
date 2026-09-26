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
        <h1 className="text-axiom-24 font-medium text-text-primary">Policies</h1>
        <p className="mt-2 max-w-2xl text-axiom-15 text-text-secondary">
          Active governance policy is read from project configuration (YAML templates). Templates below describe common
          bundles.
        </p>
      </header>

      <section className="rounded-lg border border-border bg-card p-6">
        {policyQuery.isPending ? (
          <div className="h-24 animate-pulse rounded bg-secondary" />
        ) : policyQuery.isError ? (
          <p className="font-mono text-axiom-14 text-status-denied-fg">
            {policyQuery.error instanceof Error ? policyQuery.error.message : "Could not load policy"}
          </p>
        ) : policy ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-axiom-22 font-medium text-text-primary">{policy.display_name}</h2>
                <p className="mt-1 font-mono text-axiom-13 text-text-secondary">
                  <span className="text-text-tertiary">Key</span>{" "}
                  <span className="text-text-primary">{policy.name}</span>
                  <span className="mx-2 text-text-tertiary">·</span>
                  <span className="text-text-tertiary">Version</span>{" "}
                  <span className="text-text-primary">{policy.version}</span>
                </p>
                {policy.is_default_configuration ? (
                  <p className="mt-3 font-mono text-axiom-12 text-text-tertiary">
                    Default policy — no custom policy configured in project settings.
                  </p>
                ) : null}
              </div>
              <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 font-mono text-axiom-12 uppercase tracking-wide text-status-ok-fg">
                Active
              </span>
            </div>
            <ol className="mt-6 space-y-2 font-mono text-axiom-14 text-text-primary">
              {policy.rules.length === 0 ? (
                <li className="text-text-tertiary">No rules in YAML (unexpected).</li>
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
        <h2 className="mb-4 font-mono text-axiom-16 font-medium uppercase tracking-[1px] text-text-primary">
          Available templates
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {TEMPLATES.map((t) => (
            <div
              key={t.name}
              className="rounded-lg border border-border bg-card p-5"
            >
              <h3 className="text-axiom-18 font-medium text-text-primary">{t.name}</h3>
              <p className="mt-2 text-axiom-14 text-text-secondary">{t.summary}</p>
              <ul className="mt-4 space-y-1 font-mono text-axiom-13 text-text-tertiary">
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
