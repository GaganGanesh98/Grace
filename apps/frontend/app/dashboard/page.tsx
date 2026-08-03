"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Folders } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useMemo, useState, type ReactElement } from "react";

import { ActivityTable } from "@/components/command-center/activity-table";
import { AttentionStrip } from "@/components/command-center/attention-strip";
import { CryptoFooter } from "@/components/command-center/crypto-footer";
import { EmptyStateCommandCenter } from "@/components/command-center/empty-state";
import { PostureCard } from "@/components/command-center/posture-card";
import { PolicyCard } from "@/components/command-center/policy-card";
import { CryptoHealthCard } from "@/components/command-center/crypto-health-card";
import { CodeBlock } from "@/components/code-block";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { ReceiptDrawer } from "@/components/receipt-drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { isCommandCenterEmptyState } from "@/lib/command-center-empty";
import { fetchAgentDefinitionsNonArchivedCount, fetchAllAgentDefinitions } from "@/lib/agent-runner-api";
import { apiCreateProject } from "@/lib/api";
import { fetchActiveGovernancePolicy, fetchPendingReceipts } from "@/lib/governance-api";
import { fetchGovernanceLedgerBundle } from "@/lib/governance-ledger-bundle";
import { ACTIVE_PROJECT_ID_LS_KEY, readGovernanceApiKey } from "@/lib/axiom-storage";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const EMPTY = new Map();

function formatCreatedRelative(iso: string): string {
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

function CommandCenterInner(): ReactElement {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const {
    projects,
    projectsLoading,
    projectsError,
    activeProjectId,
    activeProject,
    refreshProjects,
    governanceKeyEpoch,
  } = useProjectWorkspace();

  const [apiKey, setApiKey] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDescription, setNewProjectDescription] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [activeReceiptId, setActiveReceiptId] = useState<string | null>(null);

  const ledgerQuery = useQuery({
    queryKey: activeProjectId ? dashboardKeys.ledgerBundle(activeProjectId) : ["axiom", "ledger", "none"],
    queryFn: () => fetchGovernanceLedgerBundle(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });

  const activePolicyQuery = useQuery({
    queryKey: activeProjectId ? dashboardKeys.activePolicy(activeProjectId) : ["axiom", "active-policy", "none"],
    queryFn: () => fetchActiveGovernancePolicy(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });

  const agentDefCountQuery = useQuery({
    queryKey: ["axiom", "agent-def-count", activeProjectId],
    queryFn: () => fetchAgentDefinitionsNonArchivedCount(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });

  const agentDefNamesQuery = useQuery({
    queryKey: activeProjectId
      ? dashboardKeys.commandCenterAgentDefinitionsAll(activeProjectId)
      : ["axiom", "cc-agent-defs", "none"],
    queryFn: () => fetchAllAgentDefinitions(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });

  const pendingQuery = useQuery({
    queryKey: activeProjectId ? dashboardKeys.pendingReceipts(activeProjectId) : ["axiom", "pending", "none"],
    queryFn: () => fetchPendingReceipts(activeProjectId!),
    enabled: Boolean(activeProjectId),
    refetchInterval: 10_000,
  });

  useEffect(() => {
    setApiKey(readGovernanceApiKey());
  }, [pathname, governanceKeyEpoch, activeProjectId]);

  const receipts = ledgerQuery.data?.receipts ?? EMPTY;
  const receiptList = useMemo(() => Array.from(receipts.values()), [receipts]);

  const sorted = useMemo(() => {
    return [...receiptList].sort((a, b) => {
      const ta = new Date(a.intent.created_at).getTime();
      const tb = new Date(b.intent.created_at).getTime();
      return tb - ta;
    });
  }, [receiptList]);

  const recent = useMemo(() => sorted.slice(0, 20), [sorted]);
  const agentNameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const d of agentDefNamesQuery.data ?? []) {
      m.set(d.agent_id, d.name);
    }
    return m;
  }, [agentDefNamesQuery.data]);
  const agentNameLoadState = agentDefNamesQuery.isPending
    ? "loading"
    : agentDefNamesQuery.isError
      ? "error"
      : "ready";
  const footerReceipt = sorted.find((r) => r.status === "sealed") ?? sorted[0];
  const merkleDepth = footerReceipt?.merkle?.depth ?? "—";
  const policyLabel = activePolicyQuery.data
    ? `${activePolicyQuery.data.display_name} (${activePolicyQuery.data.version})`
    : activePolicyQuery.isPending
      ? "…"
      : "—";

  const allRecordCreatedAts = useMemo(
    () => receiptList.map((r) => r.intent.created_at),
    [receiptList],
  );

  const dataReady =
    Boolean(activeProjectId) &&
    !ledgerQuery.isPending &&
    !agentDefCountQuery.isPending &&
    !agentDefCountQuery.isError &&
    !projectsLoading;

  const showNewProjectEmptyFinal =
    dataReady && isCommandCenterEmptyState(agentDefCountQuery.data ?? 0, allRecordCreatedAts);

  const error =
    ledgerQuery.error instanceof Error
      ? ledgerQuery.error.message
      : ledgerQuery.error
        ? "Failed to load governance data"
        : null;

  const hasProjects = projects.length > 0;
  const hasKey = Boolean(apiKey);

  const pendingList = useMemo(() => pendingQuery.data ?? [], [pendingQuery.data]);
  const pendingCount = pendingList.length;
  const oldestMs = useMemo((): number | null => {
    if (pendingList.length === 0) {
      return null;
    }
    let m: number | null = null;
    for (const p of pendingList) {
      if (!p.created_at) {
        continue;
      }
      const t = new Date(p.created_at).getTime();
      if (Number.isNaN(t)) {
        continue;
      }
      if (m == null || t < m) {
        m = t;
      }
    }
    return m;
  }, [pendingList]);
  const oldestLabel = oldestMs == null ? "—" : formatCreatedRelative(new Date(oldestMs).toISOString());

  const submitCreate = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    const name = newProjectName.trim();
    if (!name) {
      toast.error("Enter a project name");
      return;
    }
    setCreatingProject(true);
    try {
      const created = await apiCreateProject(
        name,
        newProjectDescription.trim() ? newProjectDescription.trim() : undefined,
      );
      try {
        window.localStorage.setItem(ACTIVE_PROJECT_ID_LS_KEY, created.id);
      } catch {
        /* ignore */
      }
      await refreshProjects();
      toast.success("Project created");
      setNewProjectName("");
      setNewProjectDescription("");
      router.replace("/dashboard");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Could not create project");
    } finally {
      setCreatingProject(false);
    }
  };

  if (projectsError) {
    return (
      <div
        className="rounded-lg border border-[var(--axiom-danger)]/30 bg-[rgba(224,80,80,0.08)] px-4 py-3 text-axiom-15 text-[var(--axiom-danger)]"
        role="alert"
      >
        Could not load projects: {projectsError.message}
      </div>
    );
  }

  if (!hasProjects && !projectsLoading) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="text-axiom-24 font-medium text-[var(--axiom-text)]">Command center</h1>
          <p className="mt-2 text-axiom-15 text-[var(--axiom-text-muted)]">
            Create a project to scope data and use the rest of the dashboard.
          </p>
        </header>
        <form onSubmit={(e) => void submitCreate(e)} className="max-w-md space-y-3">
          <div className="space-y-2">
            <Label htmlFor="cc-project-name" className="text-[var(--axiom-text-muted)]">
              Project name
            </Label>
            <Input
              id="cc-project-name"
              placeholder="Production"
              value={newProjectName}
              onChange={(ev) => setNewProjectName(ev.target.value)}
              className="border border-[var(--axiom-border)] bg-[#04040a] text-[var(--axiom-text)]"
              autoComplete="off"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cc-project-desc" className="text-[var(--axiom-text-muted)]">
              Description <span className="text-[var(--axiom-text-dim)]">(optional)</span>
            </Label>
            <textarea
              id="cc-project-desc"
              rows={2}
              value={newProjectDescription}
              onChange={(ev) => setNewProjectDescription(ev.target.value)}
              className="w-full resize-y rounded-sm border border-[var(--axiom-border)] bg-surface-input px-3 py-2 text-axiom-15 text-[var(--axiom-text)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
            />
          </div>
          <Button type="submit" disabled={creatingProject}>
            {creatingProject ? "CREATING…" : "CREATE PROJECT"}
          </Button>
        </form>
      </div>
    );
  }

  if (hasProjects && !activeProjectId) {
    return (
      <div
        className="rounded-lg border border-[var(--axiom-warn)]/30 bg-[rgba(212,160,48,0.08)] px-4 py-3 text-axiom-15 text-[var(--axiom-text)]"
        role="status"
      >
        Select a project from the sidebar to load the command center.
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="rounded-lg border border-[var(--axiom-danger)]/30 bg-[rgba(224,80,80,0.08)] px-4 py-3 text-axiom-15 text-[var(--axiom-danger)]"
        role="alert"
      >
        {error}
        <p className="mt-2 text-axiom-14 text-[var(--axiom-text-muted)]">Try again after refreshing, or check project access.</p>
        {activeProjectId ? (
          <Button
            type="button"
            className="mt-3"
            variant="secondary"
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: dashboardKeys.ledgerBundle(activeProjectId) });
            }}
          >
            RETRY
          </Button>
        ) : null}
      </div>
    );
  }

  if (activeProjectId && (ledgerQuery.isPending || agentDefCountQuery.isPending || projectsLoading)) {
    return (
      <div
        className="min-h-[40vh] space-y-4"
        data-testid="cc-loading"
        role="status"
        aria-label="Loading command center"
      >
        <div className="h-7 w-48 max-w-full animate-pulse rounded bg-[var(--axiom-bg-card)]" />
        <div className="grid h-32 min-w-0 max-w-full gap-4 sm:grid-cols-1 lg:grid-cols-[1.2fr_1fr_1fr]">
          <div className="h-40 animate-pulse rounded-md bg-[var(--axiom-bg-card)]" />
          <div className="h-40 animate-pulse rounded-md bg-[var(--axiom-bg-card)]" />
          <div className="h-40 animate-pulse rounded-md bg-[var(--axiom-bg-card)]" />
        </div>
        <div className="h-64 animate-pulse rounded-md bg-[var(--axiom-bg-card)]" />
      </div>
    );
  }

  const agentDefError =
    activeProjectId && agentDefCountQuery.isError
      ? agentDefCountQuery.error instanceof Error
        ? agentDefCountQuery.error.message
        : "Failed to load agent count"
      : null;

  if (agentDefError) {
    return (
      <div
        className="rounded-lg border border-[var(--axiom-warn)]/30 bg-[rgba(212,160,48,0.08)] px-4 py-3 text-axiom-15 text-[var(--axiom-text)]"
        role="alert"
      >
        {agentDefError} — the command center could not load agent scope metadata
        {activeProjectId ? (
          <Button
            type="button"
            className="mt-2"
            variant="secondary"
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: ["axiom", "agent-def-count", activeProjectId] });
            }}
          >
            RETRY
          </Button>
        ) : null}
      </div>
    );
  }

  if (activeProjectId && showNewProjectEmptyFinal) {
    return (
      <div className="min-w-0 max-w-full space-y-8">
        <header>
          <h1 className="text-axiom-24 font-medium text-[var(--axiom-text)]">Command center</h1>
          <p className="mt-2 max-w-2xl text-axiom-15 text-[var(--axiom-text-muted)]">
            Operational view of governance, receipts, and project posture for the active scope.
          </p>
        </header>
        <EmptyStateCommandCenter />
        <ReceiptDrawer
          receiptId={activeReceiptId}
          projectId={activeProjectId}
          onClose={() => {
            setActiveReceiptId(null);
          }}
          returnFocusSelector={null}
        />
      </div>
    );
  }

  return (
    <div className="min-w-0 max-w-full space-y-6">
      <header>
        <h1 className="text-axiom-24 font-medium text-[var(--axiom-text)]">Command center</h1>
        <p className="mt-2 max-w-2xl text-axiom-15 text-[var(--axiom-text-muted)]">
          Operational view of signed governance. Create a project to scope data; add API keys on{" "}
          <span className="text-[var(--axiom-electric)]">Projects</span> for SDK access.
        </p>
        {!hasKey && hasProjects && activeProjectId ? (
          <p className="mt-2 text-axiom-14 text-[var(--axiom-warn)]" role="status">
            No governance API key in this browser — create one on the Projects page for SDK and agents.
          </p>
        ) : null}
      </header>

      <div className="grid min-w-0 grid-cols-1 gap-4 sm:min-w-0 lg:min-w-0 lg:grid-cols-[1.2fr_1fr_1fr]">
        <PostureCard projectId={activeProjectId} />
        <CryptoHealthCard projectId={activeProjectId} />
        <PolicyCard projectId={activeProjectId} />
      </div>

      {pendingCount > 0 ? (
        <AttentionStrip
          pendingCount={pendingCount}
          oldestLabel={oldestLabel}
          reviewHref="/dashboard/approvals"
        />
      ) : null}

      <section
        className="rounded-md border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] p-4"
        aria-labelledby="cc-recent-heading"
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="cc-recent-heading" className="text-axiom-16 font-medium text-[var(--axiom-text)]">
            Recent activity
          </h2>
          <Link
            href="/dashboard/receipts"
            className="text-axiom-14 text-text-secondary underline decoration-border-strong underline-offset-4 hover:text-text-primary"
          >
            View all
          </Link>
        </div>
        <ActivityTable
          rows={recent}
          onRowSelect={(id) => {
            setActiveReceiptId(id);
          }}
          agentsLinkHref="/dashboard/agents"
          agentNameById={agentNameById}
          agentNameLoadState={agentNameLoadState}
        />
        <CryptoFooter
          projectId={activeProjectId}
          merkleDepth={merkleDepth}
          policyLabel={policyLabel}
        />
      </section>

      {hasProjects && activeProjectId && receiptList.length === 0 && pendingCount === 0 && !hasKey ? (
        <div className="mt-2 rounded-md border border-[var(--axiom-border)]/80 bg-[var(--axiom-bg)] p-4">
          <h2 className="font-mono text-axiom-14 text-[var(--axiom-text-label)]">Getting started</h2>
          <p className="mt-1 text-axiom-15 text-[var(--axiom-text-muted)]">Install the SDK, then run your first governed agent.</p>
          <CodeBlock className="mt-2">pip install axiom-sdk</CodeBlock>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => {
          router.push("/dashboard/projects");
        }}
        className={cn(
          "w-full max-w-2xl rounded-md border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] p-4 text-left",
          "transition hover:border-[var(--axiom-electric)]/40",
        )}
        aria-label="Open projects to manage all projects, keys, and agents"
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            router.push("/dashboard/projects");
          }
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 font-mono text-axiom-12 text-[var(--axiom-electric)]">
            <Folders className="h-4 w-4" aria-hidden />
            PROJECTS
          </span>
          <span aria-hidden className="text-[var(--axiom-electric)]">→</span>
        </div>
        {activeProject ? (
          <p className="mt-3 text-axiom-15 text-[var(--axiom-text)]">{activeProject.name}</p>
        ) : null}
      </button>

      <ReceiptDrawer
        receiptId={activeReceiptId}
        projectId={activeProjectId}
        onClose={() => {
          setActiveReceiptId(null);
        }}
        returnFocusSelector={
          activeReceiptId ? `[data-receipt-row="${CSS.escape(activeReceiptId)}"]` : null
        }
      />
    </div>
  );
}

export default function CommandCenterPage(): ReactElement {
  return (
    <Suspense
      fallback={
        <div className="min-h-[30vh] space-y-4" role="status" aria-label="Loading">
          <div className="h-8 w-64 max-w-full animate-pulse rounded bg-[var(--axiom-bg-card)]" />
          <div className="h-40 max-w-full animate-pulse rounded-md bg-[var(--axiom-bg-card)]" />
        </div>
      }
    >
      <CommandCenterInner />
    </Suspense>
  );
}
