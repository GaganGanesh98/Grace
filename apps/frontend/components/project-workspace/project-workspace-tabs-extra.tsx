"use client";

import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactElement } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { createAgentDefinition, fetchAllAgentDefinitions } from "@/lib/agent-runner-api";
import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { useProjectIdFromLayout } from "@/lib/projects/project-id-context";
import { listVaultKeys } from "@/lib/vault-api";
import {
  API_MAX_PER_PAGE,
  createProjectPolicy,
  deleteProjectMember,
  deleteProjectRequest,
  fetchProject,
  fetchProjectMembers,
  fetchProjectPolicies,
  fetchAgentRunsForProject,
  fetchActiveProjectPolicy,
  patchPolicy,
  patchProjectMember,
  updateProject,
} from "@/lib/projects/project-workspace-api";
import { cn } from "@/lib/utils";

const MODELS = [
  "gpt-4o",
  "gpt-4o-mini",
  "claude-3-5-sonnet-20241022",
  "claude-3-5-haiku-20241022",
  "gemini-2.0-flash",
  "llama-3.3-70b-versatile",
] as const;

function nextMemberRole(r: string): "ADMIN" | "MEMBER" {
  if (r === "ADMIN") {
    return "MEMBER";
  }
  return "ADMIN";
}

/* ── Agents tab ── */
export function AgentsTabPanel(): ReactElement {
  const projectId = useProjectIdFromLayout();
  const sp = useSearchParams();
  const openNew = sp.get("new") === "1";
  const [modal, setModal] = useState(openNew);
  useEffect(() => {
    if (openNew) {
      setModal(true);
    }
  }, [openNew]);

  const q = useQuery({
    queryKey: dashboardKeys.agentDefinitions(projectId),
    queryFn: () => fetchAllAgentDefinitions(projectId),
  });
  const router = useRouter();

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          type="button"
          onClick={() => {
            setModal(true);
          }}
          className="font-mono text-axiom-12 uppercase text-[var(--axiom-electric)]"
        >
          + New agent
        </button>
      </div>
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))" }}
      >
        {(q.data ?? [])
          .filter((a) => !a.is_archived)
          .map((a) => (
            <div
              key={a.id}
              className="flex flex-col rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg-card)] p-4"
            >
              <button
                type="button"
                className="text-left"
                onClick={() => {
                  router.push(`/dashboard/agents/${a.agent_id}`);
                }}
              >
                <div className="flex justify-between">
                  <span className="text-axiom-15 text-[var(--axiom-text)]">{a.name}</span>
                  <span className="text-axiom-10 font-mono text-[var(--axiom-text-label)]">Active</span>
                </div>
                <p className="text-axiom-10 font-mono text-[var(--axiom-text-label)]">{a.model}</p>
                <p className="mt-1 line-clamp-2 min-h-[34px] text-axiom-13 text-[var(--axiom-text-muted)]">
                  {a.description || "—"}
                </p>
                <p className="mt-2 font-mono text-axiom-11 text-[var(--axiom-text-dim)]">
                  (stats require backend aggregates)
                </p>
              </button>
              <div className="mt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(`/dashboard/projects/${projectId}?preselectAgent=${a.id}`);
                  }}
                  className="bg-[var(--axiom-electric)] px-3 py-1 font-mono text-axiom-11 text-black"
                >
                  Run
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toast("Edit coming soon for this card — open list page");
                  }}
                  className="border border-[var(--axiom-border)] px-3 py-1 font-mono text-axiom-11"
                >
                  Edit
                </button>
              </div>
            </div>
          ))}
        <button
          type="button"
          onClick={() => {
            setModal(true);
          }}
          className="flex min-h-[200px] items-center justify-center rounded border border-dashed border-[var(--axiom-border)] font-mono text-axiom-12 text-[var(--axiom-electric)]"
        >
          + New agent
        </button>
      </div>
      {modal ? (
        <NewAgentModal projectId={projectId} onClose={() => setModal(false)} />
      ) : null}
    </div>
  );
}

function NewAgentModal({ projectId, onClose }: { projectId: string; onClose: () => void }): ReactElement {
  const qc = useQueryClient();
  const vq = useQuery({
    queryKey: ["axiom", "vault-keys", "llm"],
    queryFn: () => listVaultKeys({ kind: "llm" }),
  });
  const [name, setName] = useState("");
  const [sys, setSys] = useState("");
  const [model, setModel] = useState<string>(MODELS[0]);
  const [vk, setVk] = useState("");
  const [hard, setHard] = useState(true);
  const [err, setErr] = useState<Record<string, string>>({});
  const m = useMutation({
    mutationFn: async () => {
      if (hard) {
        /* */ void 0;
      } else {
        // eslint-disable-next-line no-console
        console.warn("hard_enforcement off: advanced");
      }
      if (!name.trim() || !sys.trim() || !vk) {
        throw new Error("validation");
      }
      return createAgentDefinition(projectId, {
        name: name.trim(),
        system_prompt: sys.trim(),
        model,
        vault_key_id: vk,
        max_iterations: 10,
        max_tokens_per_run: 100_000,
        tools_config: hard ? { hard_enforcement: true } : { hard_enforcement: false },
      });
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: dashboardKeys.agentDefinitions(projectId) });
      await qc.invalidateQueries({ queryKey: dashboardKeys.commandCenterAgentDefinitionsAll(projectId) });
      await qc.invalidateQueries({ queryKey: dashboardKeys.agentDefinitionsNonArchivedCount(projectId) });
      toast.success("Agent created");
      onClose();
    },
    onError: (e) => {
      if (e instanceof Error && e.message === "validation") {
        return;
      }
      toast.error(e instanceof Error ? e.message : "Failed");
    },
  });
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-black/60 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded border border-[var(--axiom-border-strong)] bg-[var(--axiom-bg-card)] p-6">
        <h2 className="font-mono text-axiom-12 uppercase text-[var(--axiom-text)]">New agent</h2>
        <div className="mt-4 space-y-3">
          <div>
            <span className="text-axiom-10 font-mono uppercase">Name *</span>
            <input
              className="mt-1 w-full rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg)] p-2 font-mono text-axiom-13"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
            {err.name ? <p className="text-red-400">{err.name}</p> : null}
          </div>
          <div>
            <span className="text-axiom-10 font-mono uppercase">System prompt *</span>
            <textarea
              className="mt-1 min-h-[100px] w-full rounded border border-[var(--axiom-border)] bg-[var(--axiom-bg)] p-2"
              placeholder="You are an agent that..."
              value={sys}
              onChange={(e) => {
                setSys(e.target.value);
              }}
            />
            {err.sys ? <p className="text-red-400">{err.sys}</p> : null}
          </div>
          <div>
            <span className="text-axiom-10 font-mono uppercase">Model</span>
            <select
              className="mt-1 w-full rounded border p-2"
              value={model}
              onChange={(e) => {
                setModel(e.target.value);
              }}
            >
              {MODELS.map((m0) => (
                <option key={m0} value={m0}>
                  {m0}
                </option>
              ))}
            </select>
          </div>
          <div>
            <span className="text-axiom-10 font-mono uppercase">Vault key *</span>
            <select
              className="mt-1 w-full rounded border p-2"
              value={vk}
              onChange={(e) => {
                setVk(e.target.value);
              }}
            >
              <option value="">Select…</option>
              {(vq.data ?? []).map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name} ({k.service}) {k.key_prefix}…{k.key_suffix}
                </option>
              ))}
            </select>
            {!vq.isPending && (vq.data ?? []).length === 0 ? (
              <p className="mt-2 text-axiom-12 text-[var(--axiom-text-muted)]">
                No LLM credentials in vault.{" "}
                <Link href="/dashboard/vault" className="border-b border-border-strong text-text-secondary">
                  Add one in Vault →
                </Link>
              </p>
            ) : null}
          </div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={hard}
              className="h-4 w-4 rounded-sm border border-text-primary accent-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
              onChange={(e) => setHard(e.target.checked)}
            />
            <span className="text-axiom-12">Hard enforcement</span>
          </label>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              const e2: Record<string, string> = {};
              if (!name.trim()) {
                e2.name = "Name required";
              }
              if (!sys.trim()) {
                e2.sys = "System prompt required";
              }
              if (!vk) {
                e2.vk = "Vault key required";
              }
              if (Object.keys(e2).length) {
                setErr(e2);
                return;
              }
              m.mutate();
            }}
            className="bg-[var(--axiom-electric)] px-3 py-1.5 text-black"
          >
            Create agent
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Runs tab ── */
const RUN_FILTER_KEYS = [
  { id: "all" as const, status: null as string | null, label: "All" },
  { id: "succeeded" as const, status: "succeeded" as const, label: "Completed" },
  { id: "failed" as const, status: "failed" as const, label: "Failed" },
  { id: "pending" as const, status: "pending" as const, label: "Held for approval" },
  { id: "den" as const, status: null, label: "Has denials", disabled: true },
  { id: "esc" as const, status: null, label: "Has escalations", disabled: true },
];

export function RunsTabPanel(): ReactElement {
  const projectId = useProjectIdFromLayout();
  const [qstr, setQstr] = useState("");
  const [chip, setChip] = useState<(typeof RUN_FILTER_KEYS)[number]>(RUN_FILTER_KEYS[0]);
  const fkey = `${chip.id}:${qstr}`;
  const dataQ = useQuery({
    queryKey: dashboardKeys.projectRunsList(projectId, fkey),
    queryFn: () =>
      fetchAgentRunsForProject(projectId, {
        page: 1,
        perPage: 20,
        status: chip.status ?? undefined,
        q: qstr || undefined,
      }),
  });
  const agentsQ = useQuery({
    queryKey: dashboardKeys.agentDefinitions(projectId),
    queryFn: () => fetchAllAgentDefinitions(projectId),
  });
  const nameByDef = useMemo(() => {
    const m = new Map<string, string>();
    for (const a of agentsQ.data ?? []) {
      m.set(a.id, a.name);
    }
    return m;
  }, [agentsQ.data]);

  const runs = dataQ.data?.data ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          placeholder="Search id, goal, agent…"
          className="min-w-[200px] flex-1 rounded border p-2 font-mono text-axiom-12"
          value={qstr}
          onChange={(e) => {
            setQstr(e.target.value);
          }}
        />
        {RUN_FILTER_KEYS.map((c) => (
          <button
            key={c.id}
            type="button"
            title={"disabled" in c && c.disabled ? "Not supported by API (Phase 7.12b)" : ""}
            disabled={Boolean("disabled" in c && c.disabled)}
            onClick={() => {
              if (!("disabled" in c) || !c.disabled) {
                setChip(c);
              }
            }}
            className={cn(
              "rounded border px-2 py-1 font-mono text-axiom-11",
              chip.id === c.id
                ? "border-[var(--axiom-electric)] bg-[var(--axiom-electric)]/15 text-[var(--axiom-electric)]"
                : "border-[var(--axiom-border)]",
            )}
          >
            {c.label}
          </button>
        ))}
      </div>
      {dataQ.isPending ? (
        <p className="p-4">Loading…</p>
      ) : runs.length === 0 ? (
        <p className="p-[60px] text-center text-[var(--axiom-text-muted)]">No runs match your filter.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] font-mono text-axiom-12">
            <thead>
              <tr className="border-b text-axiom-10 uppercase text-[var(--axiom-text-label)]">
                <th className="w-[110px] py-2">Time</th>
                <th className="w-[140px]">Agent</th>
                <th>Goal</th>
                <th className="w-[100px]">Verdicts</th>
                <th className="w-[120px]">Status</th>
                <th className="w-[80px]">Cost</th>
                <th className="w-[80px]" />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const g = (r.input_payload?.goal as string | undefined) ?? "—";
                return (
                  <tr
                    key={r.id}
                    className="cursor-pointer border-b hover:bg-[var(--axiom-electric)]/5"
                    onClick={() => {
                      window.location.assign(`/dashboard/ledger/${r.id}`);
                    }}
                  >
                    <td className="py-1 text-[var(--axiom-text-dim)]">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td className="truncate text-[var(--axiom-electric)]">
                      {nameByDef.get(r.agent_definition_id) ?? "—"}
                    </td>
                    <td className="max-w-xs truncate">{g}</td>
                    <td>—</td>
                    <td>{r.status}</td>
                    <td>—</td>
                    <td className="text-right">Replay</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── Policies (short) ── */
export function PoliciesTabPanel(): ReactElement {
  const projectId = useProjectIdFromLayout();
  const qc = useQueryClient();
  const pQ = useQuery({
    queryKey: dashboardKeys.projectPolicies(projectId),
    queryFn: () => fetchProjectPolicies(projectId, { perPage: API_MAX_PER_PAGE }),
  });
  const aQ = useQuery({
    queryKey: ["axiom", "governance", "active-policy", projectId],
    queryFn: () => fetchActiveProjectPolicy(projectId),
  });
  const [open, setOpen] = useState<string | null>(null);
  const [np, setNp] = useState(false);

  return (
    <div className="space-y-6">
      {aQ.data ? (
        <div className="rounded border border-[var(--axiom-electric)]/30 bg-gradient-to-r from-[var(--axiom-electric)]/10 p-4">
          <p className="text-axiom-10 font-mono uppercase text-[var(--axiom-electric)]">Active policy (YAML engine)</p>
          <h3 className="text-axiom-18 text-[var(--axiom-text)]">
            {aQ.data.display_name} ({aQ.data.version})
          </h3>
        </div>
      ) : null}
      <div className="flex justify-end">
        <button
          type="button"
          className="text-[var(--axiom-electric)]"
          onClick={() => {
            setNp(true);
          }}
        >
          + New policy
        </button>
      </div>
      {(pQ.data?.data ?? []).map((p) => (
        <div key={p.id} className="rounded border p-3">
          <div className="flex justify-between">
            <div>
              <p className="text-[var(--axiom-text)]">
                {p.name} {p.is_active ? "ACTIVE" : ""}
              </p>
              <p className="text-axiom-12 text-[var(--axiom-text-dim)]">
                {p.rules.length} rules · {p.version} v
              </p>
            </div>
            <div>
              <button
                type="button"
                className="px-2"
                onClick={() => {
                  // eslint-disable-next-line no-alert
                  alert("Policy rule editor coming in Phase 7.13");
                }}
              >
                Edit
              </button>
              {p.is_active ? null : (
                <button
                  type="button"
                  onClick={async () => {
                    if (
                      !confirm(
                        `Activate ${p.name}? This will add a new policy version in the system.`,
                      )
                    ) {
                      return;
                    }
                    await patchPolicy(projectId, p.id, { is_active: true });
                    await qc.invalidateQueries({ queryKey: dashboardKeys.projectPolicies(projectId) });
                  }}
                  className="bg-[var(--axiom-electric)] px-2 text-black"
                >
                  Activate
                </button>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setOpen((x) => (x === p.id ? null : p.id));
            }}
            className="text-axiom-11"
          >
            {open === p.id ? "Hide" : "Show"} versions
          </button>
          {open === p.id ? (
            <ul className="ml-2 mt-1 border-l border-[var(--axiom-border)] pl-2">
              <li>Version {p.id.slice(0, 8)} — {new Date(p.created_at).toLocaleString()}</li>
            </ul>
          ) : null}
        </div>
      ))}
      {np ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" onMouseDown={(e) => e.target === e.currentTarget && setNp(false)}>
          <div className="w-full max-w-md rounded border p-4">
            <NewPolicyForm
              onCancel={() => setNp(false)}
              onCreate={async (b) => {
                await createProjectPolicy(projectId, b);
                await qc.invalidateQueries({ queryKey: dashboardKeys.projectPolicies(projectId) });
                // eslint-disable-next-line no-alert
                alert("Rule editor coming in Phase 7.13 — policy created successfully");
                setNp(false);
              }}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function NewPolicyForm({
  onCreate,
  onCancel,
}: {
  onCreate: (b: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}): ReactElement {
  const [n, setN] = useState("");
  const [d, setD] = useState("");
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        await onCreate({ slug: n.toLowerCase().replace(/\s+/g, "-"), name: n, description: d, pack: "custom", rules: [] });
      }}
    >
      <h3 className="mb-2 font-mono">New policy</h3>
      <input
        className="mb-2 w-full border p-2"
        value={n}
        onChange={(e) => setN(e.target.value)}
        placeholder="name"
        required
      />
      <textarea
        className="mb-2 w-full border p-2"
        value={d}
        onChange={(e) => setD(e.target.value)}
        placeholder="description"
      />
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
        <button className="bg-[var(--axiom-electric)] text-black" type="submit">
          Create &amp; edit rules
        </button>
      </div>
    </form>
  );
}

/* ── Members ── */
export function MembersTabPanel(): ReactElement {
  const projectId = useProjectIdFromLayout();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: dashboardKeys.projectMembers(projectId),
    queryFn: () => fetchProjectMembers(projectId, { perPage: API_MAX_PER_PAGE }),
  });

  return (
    <ul className="space-y-2">
      {(q.data?.data ?? []).map((m) => (
        <li key={m.id} className="flex items-center justify-between border-b p-2">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--axiom-border)] font-mono text-axiom-12">
              {(m.full_name ?? m.user_email)
                .split(/\s+/)
                .map((p) => p[0])
                .join("")
                .slice(0, 2)
                .toUpperCase() || m.user_id.slice(0, 2)}
            </div>
            <div>
              <p className="text-axiom-13 text-[var(--axiom-text)]">
                {m.full_name || m.user_email}
              </p>
              <p className="text-axiom-10 font-mono text-[var(--axiom-text-label)]">
                {m.user_email}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={async () => {
                if (m.role === "OWNER") {
                  return;
                }
                const n = nextMemberRole(m.role);
                try {
                  await patchProjectMember(projectId, m.id, { role: n });
                  await qc.invalidateQueries({ queryKey: dashboardKeys.projectMembers(projectId) });
                } catch (e) {
                  toast.error(e instanceof Error ? e.message : "Failed");
                }
              }}
              className={cn(
                "rounded px-2 py-0.5 font-mono text-axiom-10",
                m.role === "OWNER" && "text-[var(--axiom-electric)]",
                m.role === "ADMIN" && "text-blue-300",
                m.role === "MEMBER" && "text-[var(--axiom-text-muted)]",
              )}
            >
              {m.role}
            </button>
            <button
              type="button"
              disabled={m.role === "OWNER"}
              onClick={async () => {
                if (!confirm("Remove member?")) {
                  return;
                }
                try {
                  await deleteProjectMember(projectId, m.id);
                  await qc.invalidateQueries({ queryKey: dashboardKeys.projectMembers(projectId) });
                } catch (e) {
                  toast.error(e instanceof Error ? e.message : "Failed");
                }
              }}
            >
              Remove
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ── Settings ── */
export function SettingsTabPanel(): ReactElement {
  const projectId = useProjectIdFromLayout();
  const { projectsListTotal } = useProjectWorkspace();
  const router = useRouter();
  const qc = useQueryClient();
  const pq = useQuery({
    queryKey: dashboardKeys.project(projectId),
    queryFn: () => fetchProject(projectId),
  });
  const [n, setN] = useState("");
  const [d, setD] = useState("");

  useEffect(() => {
    const p = pq.data;
    if (!p) {
      return;
    }
    setN(p.name);
    setD(p.description ?? "");
  }, [pq.data]);

  const pmut = useMutation({
    mutationFn: (body: { name: string; description: string | null }) => updateProject(projectId, body),
    onSuccess: async (p) => {
      await qc.invalidateQueries({ queryKey: dashboardKeys.project(projectId) });
      toast.success("Project updated", { description: p.name });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed"),
  });

  const canDelete = projectsListTotal > 1;

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-axiom-12 font-mono uppercase">Identity</h2>
        <div className="mt-2 space-y-2">
          <div>
            <p className="text-axiom-10">Name</p>
            <input
              className="w-full border p-2"
              value={n}
              onChange={(e) => setN(e.target.value)}
            />
          </div>
          <div>
            <p className="text-axiom-10">Description</p>
            <textarea
              className="min-h-[60px] w-full border p-2"
              value={d}
              onChange={(e) => setD(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="bg-[var(--axiom-electric)] px-3 py-1 text-black"
            onClick={() => pmut.mutate({ name: n, description: d || null })}
          >
            Save changes
          </button>
        </div>
      </section>
      <section className="border border-red-500/30 p-4">
        <h2 className="text-red-400">Danger zone</h2>
        <p className="text-axiom-13">Deleting a project is irreversible.</p>
        <button
          type="button"
          className="mt-2 text-red-400"
          onClick={async () => {
            if (!canDelete) {
              toast.error("Cannot delete your only project. Create another project first.");
              return;
            }
            const t = window.prompt("Type the project name to delete:");
            if (t !== n) {
              return;
            }
            try {
              await deleteProjectRequest(projectId);
              await qc.invalidateQueries({ queryKey: dashboardKeys.projects });
              router.push("/dashboard/projects");
            } catch (e) {
              toast.error(e instanceof Error ? e.message : "Failed");
            }
          }}
        >
          Delete project
        </button>
      </section>
    </div>
  );
}
