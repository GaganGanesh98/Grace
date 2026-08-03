"use client";

import { useQuery, useQueries, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import { apiListProjectKeys, apiListProjects, type ProjectApiKeyRow } from "@/lib/api";
import { ACTIVE_PROJECT_ID_LS_KEY } from "@/lib/axiom-storage";
import { dashboardKeys } from "@/lib/dashboard-query-keys";
import type { ListEnvelope, ProjectOut } from "@/lib/types";

export type ProjectRow = { id: string; name: string; created_at: string };

type ProjectsListSnapshot = { rows: ProjectRow[]; total: number };

type ProjectWorkspaceValue = {
  projects: ProjectRow[];
  /** Total project count from list API `meta.total` (may exceed `projects.length` when the list is paginated). */
  projectsListTotal: number;
  projectsLoading: boolean;
  projectsError: Error | null;
  activeProjectId: string | null;
  activeProject: ProjectRow | null;
  /** Updates active project in memory and localStorage (no full page reload). */
  setActiveProjectId: (id: string) => void;
  refreshProjects: () => Promise<void>;
  /** API keys per project id. */
  keysByProject: Record<string, ProjectApiKeyRow[]>;
  keysLoading: boolean;
  /** True while the active project's key list is loading (first fetch). */
  activeProjectKeysLoading: boolean;
  invalidateProjectKeys: (projectId: string) => Promise<void>;
  /** Increments when a governance API key is written so the command center re-reads storage. */
  governanceKeyEpoch: number;
  bumpGovernanceKeyEpoch: () => void;
};

const ProjectWorkspaceContext = createContext<ProjectWorkspaceValue | null>(null);

/**
 * `dashboardKeys.projects` can be written by a stray `queryFn: apiListProjects` (raw `ListEnvelope`); the provider
 * stores `ProjectsListSnapshot` from the same key. Normalizes to `{ rows, total }` in all cases.
 */
function normalizeProjectsListCache(
  data: ProjectRow[] | ListEnvelope<ProjectOut> | ProjectsListSnapshot | undefined,
): ProjectsListSnapshot {
  if (data == null) {
    return { rows: [], total: 0 };
  }
  if (Array.isArray(data)) {
    return { rows: data, total: data.length };
  }
  if ("rows" in data) {
    return data;
  }
  return {
    rows: data.data.map((p) => ({ id: p.id, name: p.name, created_at: p.created_at })),
    total: data.meta.total,
  };
}

function readStoredActiveId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACTIVE_PROJECT_ID_LS_KEY);
}

export function ProjectWorkspaceProvider({ children }: { children: ReactNode }): ReactElement {
  const queryClient = useQueryClient();
  /** Always null on first paint (SSR + client) so sidebar `<nav>` matches; sync from storage in effects. */
  const [activeProjectId, setActiveProjectIdState] = useState<string | null>(null);
  const [governanceKeyEpoch, setGovernanceKeyEpoch] = useState(0);

  const projectsQuery = useQuery({
    queryKey: dashboardKeys.projects,
    queryFn: async (): Promise<ProjectsListSnapshot> => {
      const env = await apiListProjects();
      return {
        rows: env.data.map((p) => ({ id: p.id, name: p.name, created_at: p.created_at })),
        total: env.meta.total,
      };
    },
  });

  const { rows: projects, total: projectsListTotal } = useMemo((): ProjectsListSnapshot => {
    return normalizeProjectsListCache(
      projectsQuery.data as ProjectRow[] | ListEnvelope<ProjectOut> | ProjectsListSnapshot | undefined,
    );
  }, [projectsQuery.data]);

  useEffect(() => {
    if (projectsQuery.data == null) {
      return;
    }
    setActiveProjectIdState((current) => {
      if (projects.length === 0) {
        return null;
      }
      if (current && projects.some((p) => p.id === current)) {
        return current;
      }
      const stored = readStoredActiveId()?.trim();
      if (stored && projects.some((p) => p.id === stored)) {
        return stored;
      }
      return projects[0]?.id ?? null;
    });
  }, [projectsQuery.data, projects]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (activeProjectId) {
      try {
        window.localStorage.setItem(ACTIVE_PROJECT_ID_LS_KEY, activeProjectId);
      } catch {
        /* ignore */
      }
    } else {
      try {
        window.localStorage.removeItem(ACTIVE_PROJECT_ID_LS_KEY);
      } catch {
        /* ignore */
      }
    }
  }, [activeProjectId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handler = (e: StorageEvent): void => {
      if (e.key !== ACTIVE_PROJECT_ID_LS_KEY) {
        return;
      }
      if (e.newValue === activeProjectId) {
        return;
      }
      setActiveProjectIdState(e.newValue);
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [activeProjectId]);

  const keyQueries = useQueries({
    queries: projects.map((p) => ({
      queryKey: dashboardKeys.projectKeys(p.id),
      queryFn: async (): Promise<ProjectApiKeyRow[]> => apiListProjectKeys(p.id),
      enabled: projects.length > 0 && Boolean(projectsQuery.isSuccess),
    })),
  });

  const keysByProject = useMemo((): Record<string, ProjectApiKeyRow[]> => {
    const out: Record<string, ProjectApiKeyRow[]> = {};
    projects.forEach((p, i) => {
      const q = keyQueries[i];
      out[p.id] = q?.data ?? [];
    });
    return out;
  }, [projects, keyQueries]);

  const keysLoading = keyQueries.some((q) => q.isLoading || q.isFetching);

  const activeProjectKeysLoading = useMemo((): boolean => {
    if (!activeProjectId) {
      return false;
    }
    const idx = projects.findIndex((p) => p.id === activeProjectId);
    if (idx < 0) {
      return false;
    }
    return Boolean(keyQueries[idx]?.isPending);
  }, [activeProjectId, projects, keyQueries]);

  const setActiveProjectId = useCallback((id: string): void => {
    setActiveProjectIdState(id);
  }, []);

  const refreshProjects = useCallback(async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: dashboardKeys.projects });
  }, [queryClient]);

  const invalidateProjectKeys = useCallback(
    async (projectId: string): Promise<void> => {
      await queryClient.invalidateQueries({ queryKey: dashboardKeys.projectKeys(projectId) });
    },
    [queryClient],
  );

  const bumpGovernanceKeyEpoch = useCallback((): void => {
    setGovernanceKeyEpoch((n) => n + 1);
  }, []);

  const activeProject = useMemo(
    () => projects.find((p) => p.id === activeProjectId) ?? null,
    [projects, activeProjectId],
  );

  const projectsError = useMemo((): Error | null => {
    if (projectsQuery.error instanceof Error) {
      return projectsQuery.error;
    }
    if (projectsQuery.error) {
      return new Error("Failed to load projects");
    }
    return null;
  }, [projectsQuery.error]);

  const value = useMemo(
    (): ProjectWorkspaceValue => ({
      projects,
      projectsListTotal,
      projectsLoading: projectsQuery.isPending || (projectsQuery.isFetching && projects.length === 0),
      projectsError,
      activeProjectId,
      activeProject,
      setActiveProjectId,
      refreshProjects,
      keysByProject,
      keysLoading,
      activeProjectKeysLoading,
      invalidateProjectKeys,
      governanceKeyEpoch,
      bumpGovernanceKeyEpoch,
    }),
    [
      projects,
      projectsListTotal,
      projectsQuery.isPending,
      projectsQuery.isFetching,
      projectsError,
      activeProjectId,
      activeProject,
      setActiveProjectId,
      refreshProjects,
      keysByProject,
      keysLoading,
      activeProjectKeysLoading,
      invalidateProjectKeys,
      governanceKeyEpoch,
      bumpGovernanceKeyEpoch,
    ],
  );

  return (
    <ProjectWorkspaceContext.Provider value={value}>{children}</ProjectWorkspaceContext.Provider>
  );
}

export function useProjectWorkspace(): ProjectWorkspaceValue {
  const ctx = useContext(ProjectWorkspaceContext);
  if (!ctx) {
    throw new Error("useProjectWorkspace must be used within ProjectWorkspaceProvider");
  }
  return ctx;
}
