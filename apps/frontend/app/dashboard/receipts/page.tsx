"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useMemo, useState, type ReactElement } from "react";

import { GovernanceReceiptDrawer } from "@/components/receipts/receipt-drawer";
import { VerdictStatusPill } from "@/components/receipts/verdict-status-pill";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { listReceipts, type ReceiptVerdict } from "@/lib/receipts-api";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;

const VERDICT_TABS: Array<{ id: "all" | ReceiptVerdict; label: string }> = [
  { id: "all", label: "All" },
  { id: "AUTHORIZED", label: "AUTHORIZED" },
  { id: "DENIED", label: "DENIED" },
  { id: "HELD", label: "HELD" },
];

function formatReceiptId(id: string): string {
  if (id.length <= 14) {
    return id;
  }
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

function formatSealedRelative(iso: string | null): string {
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

function verdictDotClass(v: ReceiptVerdict): string {
  if (v === "AUTHORIZED") {
    return "bg-status-ok-fg";
  }
  if (v === "DENIED") {
    return "bg-status-denied-fg";
  }
  return "bg-status-held-fg";
}

function httpClass(status: number): string {
  if (status >= 400) {
    return "text-status-denied-fg";
  }
  if (status >= 200 && status < 300) {
    return "text-status-ok-fg";
  }
  return "text-text-primary";
}

function ReceiptsPageInner(): ReactElement {
  const queryClient = useQueryClient();
  const { projects, projectsLoading, projectsError, activeProjectId } = useProjectWorkspace();
  const [projectScope, setProjectScope] = useState<"all" | string>("all");
  const [verdictTab, setVerdictTab] = useState<"all" | ReceiptVerdict>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [drawerId, setDrawerId] = useState<string | null>(null);

  const scopeIds = useMemo(() => {
    if (projectScope === "all") {
      return projects.map((p) => p.id);
    }
    return [projectScope];
  }, [projectScope, projects]);

  const scopeKey = projectScope === "all" ? `all:${projects.map((p) => p.id).sort().join(",")}` : projectScope;

  const listQuery = useQuery({
    queryKey: ["axiom", "receipts-page", scopeKey],
    queryFn: () =>
      listReceipts({
        project_ids: scopeIds.length ? scopeIds : undefined,
        limit: 10_000,
        offset: 0,
      }),
    enabled: scopeIds.length > 0 && !projectsLoading,
  });

  const rawItems = useMemo(() => listQuery.data?.items ?? [], [listQuery.data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = rawItems;
    if (verdictTab !== "all") {
      rows = rows.filter((r) => r.verdict === verdictTab);
    }
    if (q) {
      rows = rows.filter((r) => {
        const hay = `${r.id} ${r.upstream_model} ${r.upstream_provider} ${r.action_type}`.toLowerCase();
        return hay.includes(q);
      });
    }
    return rows;
  }, [rawItems, verdictTab, search]);

  const totalFiltered = filtered.length;
  const pageCount = Math.max(1, Math.ceil(totalFiltered / PAGE_SIZE));

  useEffect(() => {
    setPage((p) => Math.min(p, Math.max(0, pageCount - 1)));
  }, [pageCount]);

  const safePage = Math.min(page, Math.max(0, pageCount - 1));
  const pageItems = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, safePage]);

  const drawerProjectId = useMemo(() => {
    if (!drawerId) {
      return null;
    }
    return rawItems.find((x) => x.id === drawerId)?.project_id ?? activeProjectId;
  }, [drawerId, rawItems, activeProjectId]);

  if (projectsError) {
    return (
      <div className="text-body text-[var(--status-denied-fg)]" role="alert">
        Could not load projects: {projectsError.message}
      </div>
    );
  }

  if (!projectsLoading && projects.length === 0) {
    return (
      <div className="space-y-4 px-8 pt-6">
        <h1 className="text-display text-text-primary">Receipts</h1>
        <p className="text-body text-text-secondary">Create a project first to collect governance receipts.</p>
        <Link
          href="/dashboard/projects"
          className="inline-flex rounded-sm border border-border px-4 py-2 text-body font-medium uppercase tracking-[1px] text-text-primary hover:border-border-strong hover:bg-surface-elevated"
        >
          Open projects
        </Link>
      </div>
    );
  }

  const loading = projectsLoading || (scopeIds.length > 0 && listQuery.isPending);
  const errorMsg =
    listQuery.error instanceof Error
      ? listQuery.error.message
      : listQuery.error
        ? "Failed to load receipts"
        : null;

  const startN = totalFiltered === 0 ? 0 : safePage * PAGE_SIZE + 1;
  const endN = Math.min(totalFiltered, (safePage + 1) * PAGE_SIZE);

  return (
    <div className="min-w-0 px-8 pb-10 pt-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-display text-text-primary">Receipts</h1>
          <p className="mt-1 max-w-2xl text-body text-text-secondary">
            Cryptographic audit trail for governed agent actions. Ed25519 + ML-DSA-65 hybrid signatures, NIST PQC Level
            3.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-body-s text-text-tertiary tabular-nums">{rawItems.length} receipts</span>
          <Button type="button" variant="secondary" size="sm" disabled title="Select a receipt to verify">
            Verify
          </Button>
        </div>
      </header>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border-subtle)]">
        <nav className="flex flex-wrap gap-1" aria-label="Verdict filter">
          {VERDICT_TABS.map((t) => {
            const active = verdictTab === t.id;
            return (
              <button
                key={t.label}
                type="button"
                className={cn(
                  "border-b-2 px-4 py-3 text-body font-medium transition-colors duration-instant ease-default",
                  active
                    ? "border-text-primary text-text-primary"
                    : "border-transparent text-text-secondary hover:border-[var(--border-default)] hover:text-text-primary",
                )}
                onClick={() => {
                  setVerdictTab(t.id);
                  setPage(0);
                }}
              >
                {t.label}
              </button>
            );
          })}
        </nav>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <label className="sr-only" htmlFor="receipts-project-scope">
            Project
          </label>
          <select
            id="receipts-project-scope"
            className="h-9 w-[200px] rounded-sm border border-[var(--border-default)] bg-surface-input px-3 text-body text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-100"
            value={projectScope}
            onChange={(e) => {
              const v = e.target.value;
              setProjectScope(v === "all" ? "all" : v);
              setPage(0);
            }}
          >
            <option value="all">All projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <Input
            className="h-9 w-[240px] border-[var(--border-default)] bg-surface-input text-body"
            placeholder="Search receipt ID, model, provider…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            aria-label="Search receipts"
          />
        </div>
      </div>

      {errorMsg ? (
        <div className="mt-6 rounded-md border border-[var(--status-denied-border)] bg-status-denied-bg px-4 py-3 text-body text-[var(--status-denied-fg)]">
          Failed to load receipts. Try again.
          <Button
            type="button"
            variant="secondary"
            className="ml-3"
            onClick={() => void queryClient.invalidateQueries({ queryKey: ["axiom", "receipts-page", scopeKey] })}
          >
            Retry
          </Button>
        </div>
      ) : null}

      {loading && !errorMsg ? (
        <div className="mt-6 overflow-hidden rounded-md border border-[var(--border-subtle)] bg-surface-card">
          <div className="h-8 bg-surface-elevated" />
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-9 border-b border-[var(--border-subtle)] px-4">
              <div className="my-2 h-4 animate-pulse rounded bg-surface-elevated" />
            </div>
          ))}
        </div>
      ) : null}

      {!loading && !errorMsg && totalFiltered === 0 && rawItems.length === 0 ? (
        <div className="mt-10 flex flex-col items-center text-center">
          <ShieldCheck className="h-12 w-12 text-text-tertiary" aria-hidden />
          <h2 className="mt-4 text-section text-text-primary">No receipts yet</h2>
          <p className="mt-2 max-w-md text-body text-text-secondary">
            Receipts appear here when agents execute governed actions.
          </p>
          <Link
            href="/dashboard/projects"
            className="mt-4 text-body text-text-secondary underline decoration-[var(--border-strong)] underline-offset-4 hover:text-text-primary"
          >
            Create an agent →
          </Link>
        </div>
      ) : null}

      {!loading && !errorMsg && totalFiltered === 0 && rawItems.length > 0 ? (
        <div className="mt-6 text-body text-text-secondary">No receipts match the current filters.</div>
      ) : null}

      {!loading && !errorMsg && pageItems.length > 0 ? (
        <>
          <div className="mt-6 overflow-hidden rounded-md border border-[var(--border-subtle)] bg-surface-card">
            <table className="w-full min-w-[900px] border-separate border-spacing-0 text-left tabular-nums">
              <caption className="sr-only">Governance receipts</caption>
              <thead>
                <tr className="h-8 bg-surface-elevated text-micro uppercase text-text-secondary">
                  <th scope="col" className="w-6 px-4 text-left font-semibold">
                    {" "}
                  </th>
                  <th scope="col" className="w-[140px] px-2 text-left font-semibold">
                    Receipt ID
                  </th>
                  <th scope="col" className="w-[100px] px-2 text-left font-semibold">
                    Verdict
                  </th>
                  <th scope="col" className="w-[160px] px-2 text-left font-semibold">
                    Action
                  </th>
                  <th scope="col" className="w-[140px] px-2 text-left font-semibold">
                    Model
                  </th>
                  <th scope="col" className="w-[80px] px-2 text-right font-semibold">
                    Tokens
                  </th>
                  <th scope="col" className="w-[56px] px-2 text-right font-semibold">
                    HTTP
                  </th>
                  <th scope="col" className="w-[80px] px-2 text-right font-semibold">
                    Latency
                  </th>
                  <th scope="col" className="w-[100px] px-2 text-right font-semibold">
                    Sealed
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((r) => (
                  <tr
                    key={r.id}
                    data-receipt-row={r.id}
                    className="h-9 cursor-pointer border-b border-[var(--border-subtle)] transition-colors duration-instant ease-default hover:bg-surface-elevated"
                    onClick={() => setDrawerId(r.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setDrawerId(r.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <td className="px-4">
                      <span className={cn("block h-1.5 w-1.5 rounded-pill", verdictDotClass(r.verdict))} title={r.verdict} />
                    </td>
                    <td className="px-2 font-mono text-mono-caption text-text-primary">{formatReceiptId(r.id)}</td>
                    <td className="px-2">
                      <VerdictStatusPill verdict={r.verdict} />
                    </td>
                    <td className="max-w-[160px] truncate px-2 font-mono text-body text-text-primary">{r.action_type}</td>
                    <td className="max-w-[140px] truncate px-2 text-body text-text-primary">{r.upstream_model || "—"}</td>
                    <td className="px-2 text-right text-body text-text-primary">
                      {r.total_tokens == null ? "—" : r.total_tokens}
                    </td>
                    <td className={cn("px-2 text-right text-body", httpClass(r.upstream_status))}>{r.upstream_status || "—"}</td>
                    <td className="px-2 text-right text-body text-text-secondary">{r.upstream_latency_ms}ms</td>
                    <td className="px-2 text-right font-sans text-body-s text-text-secondary">{formatSealedRelative(r.sealed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-body-s text-text-secondary">
            <span className="tabular-nums">
              Showing {startN}-{endN} of {totalFiltered}
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={safePage <= 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Prev
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={safePage >= pageCount - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      ) : null}

      <GovernanceReceiptDrawer
        receiptId={drawerId}
        projectId={drawerProjectId}
        onClose={() => setDrawerId(null)}
      />
    </div>
  );
}

export default function ReceiptsPage(): ReactElement {
  return (
    <Suspense
      fallback={
        <div className="px-8 pt-6 text-body text-text-secondary" role="status">
          Loading…
        </div>
      }
    >
      <ReceiptsPageInner />
    </Suspense>
  );
}
