"use client";

import Link from "next/link";
import { notFound, usePathname } from "next/navigation";
import { useCallback, useEffect, useState, type ReactElement, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { fetchGovernanceLedgerBundle } from "@/lib/governance-ledger-bundle";
import { fetchAgentDefinitionsNonArchivedCount } from "@/lib/agent-runner-api";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { useProjectIdFromLayout } from "@/lib/projects/project-id-context";
import { API_MAX_PER_PAGE, fetchProject, fetchAgentRunsForProject } from "@/lib/projects/project-workspace-api";
import { cn } from "@/lib/utils";

const TABS = [
  { seg: "" as const, label: "Overview" },
  { seg: "agents" as const, label: "Agents" },
  { seg: "runs" as const, label: "Runs" },
  { seg: "policies" as const, label: "Policies" },
  { seg: "members" as const, label: "Members" },
  { seg: "settings" as const, label: "Settings" },
] as const;

export function ProjectWorkspaceShell({ children }: { children: ReactNode }): ReactElement {
  const projectId = useProjectIdFromLayout();
  const pathname = usePathname();
  const { setActiveProjectId } = useProjectWorkspace();
  const qc = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);

  const projectQ = useQuery({
    queryKey: dashboardKeys.project(projectId),
    queryFn: () => fetchProject(projectId),
    retry: false,
  });

  const agentCountQ = useQuery({
    queryKey: dashboardKeys.agentDefinitionsNonArchivedCount(projectId),
    queryFn: () => fetchAgentDefinitionsNonArchivedCount(projectId),
    enabled: Boolean(projectId) && projectQ.isSuccess,
  });

  const runsTodayQ = useQuery({
    queryKey: dashboardKeys.projectHeader(projectId),
    queryFn: async () => {
      const env = await fetchAgentRunsForProject(projectId, { page: 1, perPage: API_MAX_PER_PAGE });
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
      const n = env.data.filter((r) => {
        const t = r.started_at ?? r.created_at;
        if (!t) {
          return false;
        }
        return new Date(t).getTime() >= start;
      }).length;
      return n;
    },
    enabled: Boolean(projectId) && projectQ.isSuccess,
  });

  const receiptCountQ = useQuery({
    queryKey: dashboardKeys.ledgerBundle(projectId),
    queryFn: () => fetchGovernanceLedgerBundle(projectId),
    enabled: Boolean(projectId) && projectQ.isSuccess,
  });

  useEffect(() => {
    if (projectId) {
      setActiveProjectId(projectId);
    }
  }, [projectId, setActiveProjectId]);

  useEffect(() => {
    if (projectQ.isError) {
      const e = projectQ.error as Error;
      if (e.message.toLowerCase().includes("not found") || e.message.includes("404")) {
        notFound();
      }
    }
  }, [projectQ.isError, projectQ.error]);

  const project = projectQ.data;
  const title = project?.name ?? "—";
  const desc = project?.description?.trim() || "No description.";

  const em = "text-[var(--axiom-electric)] font-mono";
  const agentN = agentCountQ.isPending ? "—" : agentCountQ.isError ? "—" : String(agentCountQ.data ?? "—");
  const runsN = runsTodayQ.isPending ? "—" : runsTodayQ.isError ? "—" : String(runsTodayQ.data ?? "—");
  const recN = receiptCountQ.isPending
    ? "—"
    : receiptCountQ.isError
      ? "—"
      : String(receiptCountQ.data?.receipts.size ?? "—");

  const onInvite = useCallback((): void => {
    setInviteOpen(true);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        setInviteOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (projectQ.isPending && !project) {
    return (
      <div className="min-h-[40vh] animate-pulse rounded-lg border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)]" />
    );
  }
  if (projectQ.isError && !project) {
    return <p className="font-mono text-sm text-red-400">{(projectQ.error as Error).message}</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <nav className="font-mono text-[10px] uppercase tracking-[2px] text-[var(--axiom-text-label)]">
          <Link
            href="/dashboard/projects"
            className="text-[var(--axiom-electric)] transition hover:underline"
          >
            Projects
          </Link>
          <span className="text-[var(--axiom-text-dim)]"> / </span>
          <span className="text-[var(--axiom-text-muted)]">{title.toUpperCase()}</span>
        </nav>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1
              className="font-[family-name:var(--font-sans)] text-[28px] font-normal text-[var(--axiom-text)]"
              style={{ fontWeight: 400 }}
            >
              {title}
            </h1>
            <p className="mt-2 max-w-3xl font-mono text-axiom-13 leading-relaxed text-[var(--axiom-text-muted)]">
              {desc}{" "}
              <span className={em}>{agentN}</span> agents · <span className={em}>{runsN}</span> runs today
              {" · "}
              <span className={em}>{recN}</span> signed receipts.
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <Link
              href={`/dashboard/projects/${projectId}/settings`}
              className="inline-flex h-9 items-center justify-center border border-[var(--axiom-border-strong)] bg-transparent px-4 font-mono text-axiom-11 uppercase tracking-wider text-[var(--axiom-text)] transition hover:border-[var(--axiom-electric)]/50"
            >
              Settings
            </Link>
            <button
              type="button"
              onClick={onInvite}
              className="inline-flex h-9 items-center justify-center bg-[var(--axiom-electric)] px-4 font-mono text-axiom-11 font-medium uppercase tracking-wider text-black transition hover:brightness-110"
            >
              + Invite
            </button>
          </div>
        </div>
      </header>

      <nav
        className="flex flex-wrap gap-1 border-b border-[var(--axiom-border)]"
        aria-label="Project workspace"
      >
        {TABS.map((t) => {
          const base =
            t.seg === ""
              ? `/dashboard/projects/${projectId}`
              : `/dashboard/projects/${projectId}/${t.seg}`;
          const pathBase = `/dashboard/projects/${projectId}`;
          const reallyActive =
            t.seg === ""
              ? pathname === pathBase || pathname === `${pathBase}/`
              : pathname === base || pathname.startsWith(`${base}/`);
          return (
            <Link
              key={t.seg}
              href={base}
              className={cn(
                "relative -mb-px border-b-2 border-transparent px-3 py-2.5 font-mono text-axiom-12 uppercase tracking-wide text-[var(--axiom-text-muted)] transition hover:text-[var(--axiom-text)]",
                reallyActive && "border-b-text-primary font-semibold text-text-primary",
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>

      {children}

      {inviteOpen ? (
        <InviteMemberModal
          projectId={projectId}
          onClose={() => {
            setInviteOpen(false);
          }}
          onInvited={async () => {
            setInviteOpen(false);
            await qc.invalidateQueries({ queryKey: dashboardKeys.projectMembers(projectId) });
            toast.success("Member invited");
          }}
        />
      ) : null}
    </div>
  );
}

function InviteMemberModal({
  projectId,
  onClose,
  onInvited,
}: {
  projectId: string;
  onClose: () => void;
  onInvited: () => void;
}): ReactElement {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"ADMIN" | "MEMBER">("ADMIN");
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="w-full max-w-md rounded border border-[var(--axiom-border-strong)] bg-[var(--axiom-bg-card)] p-6">
        <div className="flex items-center justify-between border-b border-[var(--axiom-border)] pb-3">
          <h2 className="font-mono text-axiom-12 uppercase tracking-[1.5px] text-[var(--axiom-text)]">
            Invite member
          </h2>
          <button
            type="button"
            className="text-[var(--axiom-text-muted)] hover:text-[var(--axiom-text)]"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="mt-4 space-y-3">
          <div>
            <label className="font-mono text-axiom-10 uppercase text-[var(--axiom-text-label)]">Email</label>
            <input
              className="mt-1 w-full rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg)] px-3 py-2 font-mono text-axiom-13 text-[var(--axiom-text)]"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setErr(null);
              }}
            />
            {err ? <p className="mt-1 text-axiom-12 text-red-400">{err}</p> : null}
          </div>
          <div>
            <p className="font-mono text-axiom-10 uppercase text-[var(--axiom-text-label)]">Role</p>
            <div className="mt-1 flex flex-wrap gap-2">
              {(
                [
                  ["MEMBER", "Viewer"],
                  ["ADMIN", "Admin"],
                ] as const
              ).map(([v, l]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => {
                    setRole(v);
                  }}
                  className={cn(
                    "rounded border px-3 py-1 font-mono text-axiom-11",
                    role === v
                      ? "border-text-primary bg-surface-elevated text-text-primary"
                      : "border-[var(--axiom-border)] text-[var(--axiom-text-muted)]",
                  )}
                >
                  {l}
                </button>
              ))}
            </div>
            <p className="mt-2 font-mono text-axiom-11 text-[var(--axiom-text-dim)]">
              Viewer = read-only · Admin = can create agents, run, manage policies
            </p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2 border-t border-[var(--axiom-border)] pt-4">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 font-mono text-axiom-12 text-[var(--axiom-text-muted)]"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={async () => {
              if (!email.includes("@")) {
                setErr("Valid email required");
                return;
              }
              setPending(true);
              try {
                const { inviteProjectMember } = await import("@/lib/projects/project-workspace-api");
                await inviteProjectMember(projectId, { email: email.trim(), role });
                onInvited();
              } catch (e) {
                const m = e instanceof Error ? e.message : "Failed";
                if (m.toLowerCase().includes("already")) {
                  setErr(`${email} already invited`);
                } else {
                  setErr(m);
                }
              } finally {
                setPending(false);
              }
            }}
            className="bg-[var(--axiom-electric)] px-4 py-2 font-mono text-axiom-12 font-medium uppercase text-black"
          >
            Send invite
          </button>
        </div>
      </div>
    </div>
  );
}
