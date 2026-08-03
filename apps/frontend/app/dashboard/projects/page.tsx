"use client";

import { useQueries } from "@tanstack/react-query";
import { ChevronRight, Folders } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useMemo, useState, type ReactElement } from "react";
import { toast } from "sonner";

import { useProjectWorkspace } from "@/components/project-workspace-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchAgentDefinitionsNonArchivedCount } from "@/lib/agent-runner-api";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import { apiCreateProject } from "@/lib/api";
import { ACTIVE_PROJECT_ID_LS_KEY } from "@/lib/axiom-storage";
import { useRouter, useSearchParams } from "next/navigation";

function ProjectsPageInner(): ReactElement {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { projects, projectsLoading, activeProjectId, refreshProjects, keysByProject } =
    useProjectWorkspace();

  const [showCreateProject, setShowCreateProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDescription, setNewProjectDescription] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);

  useEffect(() => {
    if (searchParams.get("new") === "1") {
      setShowCreateProject(true);
    }
  }, [searchParams]);

  async function submitCreateProject(e: React.FormEvent): Promise<void> {
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
      setShowCreateProject(false);
      setNewProjectName("");
      setNewProjectDescription("");
      toast.success("Project created");
      router.push(`/dashboard/projects/${created.id}`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Could not create project");
    } finally {
      setCreatingProject(false);
    }
  }

  const sortedProjects = useMemo(
    () => [...projects].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [projects],
  );

  const definitionCountQueries = useQueries({
    queries: projects.map((p) => ({
      queryKey: dashboardKeys.agentDefinitionsNonArchivedCount(p.id),
      queryFn: () => fetchAgentDefinitionsNonArchivedCount(p.id),
      enabled: projects.length > 0 && !projectsLoading,
    })),
  });

  function definitionCountForProject(projectId: string): number | "…" {
    const i = projects.findIndex((p) => p.id === projectId);
    if (i < 0) {
      return 0;
    }
    const q = definitionCountQueries[i];
    if (q?.isPending && q.data === undefined) {
      return "…";
    }
    return q?.data ?? 0;
  }

  return (
    <div className="space-y-10">
      <nav className="font-mono text-axiom-12 uppercase tracking-[1px] text-[#6B7490]">
        <Link className="text-[var(--axiom-electric)] hover:underline" href="/dashboard">
          Command center
        </Link>
        <span className="mx-2">/</span>
        <span className="text-[#A0A8BC]">Projects</span>
      </nav>

      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-axiom-24 font-medium text-[#F0F2F8]">Projects</h1>
          <p className="mt-2 max-w-2xl text-axiom-15 text-[#A0A8BC]">
            Manage projects, API keys, and agents
          </p>
        </div>
        <Button
          type="button"
          onClick={() => {
            setShowCreateProject((v) => !v);
          }}
        >
          + NEW PROJECT
        </Button>
      </header>

      {showCreateProject ? (
        <section className="max-w-xl space-y-4 rounded-md border border-border-subtle bg-surface-card p-4">
          <h2 className="font-mono text-axiom-14 font-medium uppercase tracking-[1px] text-[#F0F2F8]">
            New project
          </h2>
          <form onSubmit={(e) => void submitCreateProject(e)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="proj-name" className="text-[#A0A8BC]">
                Name
              </Label>
              <Input
                id="proj-name"
                value={newProjectName}
                onChange={(ev) => setNewProjectName(ev.target.value)}
                className="border-[rgba(255,255,255,0.08)] bg-[#04040a] text-[#F0F2F8]"
                placeholder="Production"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="proj-desc" className="text-[#A0A8BC]">
                Description <span className="font-normal text-[#6B7490]">(optional)</span>
              </Label>
              <textarea
                id="proj-desc"
                rows={2}
                value={newProjectDescription}
                onChange={(ev) => setNewProjectDescription(ev.target.value)}
                className="w-full resize-y rounded-sm border border-border bg-surface-input px-3 py-2 font-[family-name:var(--font-sans)] text-axiom-15 text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={creatingProject}>
                {creatingProject ? "CREATING…" : "CREATE"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowCreateProject(false);
                }}
              >
                CANCEL
              </Button>
            </div>
          </form>
        </section>
      ) : null}

      {projectsLoading ? (
        <div className="h-40 animate-pulse rounded-md bg-[#0A0A14]" />
      ) : sortedProjects.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-md border border-[rgba(255,255,255,0.06)] bg-[#0A0A14] px-6 py-16 text-center">
          <Folders className="h-12 w-12 text-[#6B7490]" aria-hidden />
          <p className="mt-4 text-axiom-18 font-medium text-[#F0F2F8]">No projects yet</p>
          <Button type="button" className="mt-6" onClick={() => setShowCreateProject(true)}>
            CREATE YOUR FIRST PROJECT
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {sortedProjects.map((p) => {
            const isActive = p.id === activeProjectId;
            const keys = keysByProject[p.id] ?? [];
            const defN = definitionCountForProject(p.id);
            return (
              <Link
                key={p.id}
                href={`/dashboard/projects/${p.id}`}
                className="flex w-full items-center justify-between gap-3 rounded-md border border-[rgba(255,255,255,0.08)] bg-[#0A0A14] px-4 py-4 text-left transition hover:border-border-strong"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={isActive ? "text-[var(--axiom-electric)]" : "text-[#6B7490]"} aria-hidden>
                      {isActive ? "●" : "○"}
                    </span>
                    <span className="font-[family-name:var(--font-sans)] text-axiom-18 font-medium text-[#F0F2F8]">
                      {p.name}
                    </span>
                    {isActive ? (
                      <span className="rounded-xs border border-text-primary bg-surface-elevated px-2 py-0.5 font-mono text-axiom-10 uppercase tracking-wide text-text-primary">
                        Active
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 truncate font-mono text-axiom-12 text-[#A0A8BC]">{p.id}</p>
                  <p className="mt-0.5 font-mono text-axiom-12 text-[#6B7490]">
                    Created {new Date(p.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2 font-mono text-axiom-12 text-[#A0A8BC]">
                  {keys.length} keys · {defN === "…" ? "…" : defN} agents
                  <ChevronRight className="h-4 w-4 text-[#6B7490]" aria-hidden />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ProjectsPage(): ReactElement {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <div className="h-8 w-48 animate-pulse rounded bg-[#0A0A14]" />
          <div className="h-40 animate-pulse rounded-md bg-[#0A0A14]" />
        </div>
      }
    >
      <ProjectsPageInner />
    </Suspense>
  );
}
