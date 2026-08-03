import { parseApiError } from "@/lib/api";
import type { AgentRunOut, DataEnvelope, ListEnvelope, ProjectOut } from "@/lib/types";
import type { ActiveGovernancePolicyPayload } from "@/lib/governance-types";
import { fetchActiveGovernancePolicy } from "@/lib/governance-api";

/** Must stay within FastAPI `Query(..., ge=1, le=100)` on paginated project routes. */
export const API_MAX_PER_PAGE = 100;

async function parseJsonOrThrow<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return res.json() as Promise<T>;
}

export async function fetchProject(projectId: string): Promise<ProjectOut> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    credentials: "include",
    cache: "no-store",
  });
  const env = await parseJsonOrThrow<DataEnvelope<ProjectOut>>(res);
  return env.data;
}

export type ProjectMemberRow = {
  id: string;
  project_id: string;
  user_id: string;
  role: string;
  joined_at: string;
  user_email: string;
  full_name: string | null;
};

export async function fetchProjectMembers(
  projectId: string,
  init?: { page?: number; perPage?: number },
): Promise<ListEnvelope<ProjectMemberRow>> {
  const p = new URLSearchParams();
  p.set("page", String(init?.page ?? 1));
  p.set("per_page", String(init?.perPage ?? API_MAX_PER_PAGE));
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/members?${p.toString()}`, {
    credentials: "include",
    cache: "no-store",
  });
  return parseJsonOrThrow<ListEnvelope<ProjectMemberRow>>(res);
}

export type PolicyOutRow = {
  id: string;
  project_id: string;
  slug: string;
  name: string;
  description: string | null;
  version: number;
  rules: unknown[];
  is_active: boolean;
  pack: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export async function fetchProjectPolicies(
  projectId: string,
  init?: { page?: number; perPage?: number },
): Promise<ListEnvelope<PolicyOutRow>> {
  const p = new URLSearchParams();
  p.set("page", String(init?.page ?? 1));
  p.set("per_page", String(init?.perPage ?? API_MAX_PER_PAGE));
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/policies?${p.toString()}`,
    { credentials: "include", cache: "no-store" },
  );
  return parseJsonOrThrow<ListEnvelope<PolicyOutRow>>(res);
}

export async function updateProject(
  projectId: string,
  body: { name?: string; description?: string | null },
): Promise<ProjectOut> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
    cache: "no-store",
  });
  const env = await parseJsonOrThrow<DataEnvelope<ProjectOut>>(res);
  return env.data;
}

export async function deleteProjectRequest(projectId: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
    credentials: "include",
    cache: "no-store",
  });
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
}

export async function patchPolicy(
  projectId: string,
  policyId: string,
  body: Record<string, unknown>,
): Promise<PolicyOutRow> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/policies/${encodeURIComponent(policyId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "include",
      cache: "no-store",
    },
  );
  const env = await parseJsonOrThrow<DataEnvelope<PolicyOutRow>>(res);
  return env.data;
}

export async function createProjectPolicy(
  projectId: string,
  body: Record<string, unknown>,
): Promise<PolicyOutRow> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/policies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
    cache: "no-store",
  });
  const env = await parseJsonOrThrow<DataEnvelope<PolicyOutRow>>(res);
  return env.data;
}

export async function inviteProjectMember(
  projectId: string,
  body: { email: string; role: string },
): Promise<ProjectMemberRow> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
    cache: "no-store",
  });
  const env = await parseJsonOrThrow<DataEnvelope<ProjectMemberRow>>(res);
  return env.data;
}

export async function patchProjectMember(
  projectId: string,
  memberId: string,
  body: { role: string },
): Promise<ProjectMemberRow> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/members/${encodeURIComponent(memberId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "include",
      cache: "no-store",
    },
  );
  const env = await parseJsonOrThrow<DataEnvelope<ProjectMemberRow>>(res);
  return env.data;
}

export async function deleteProjectMember(projectId: string, memberId: string): Promise<void> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/members/${encodeURIComponent(memberId)}`,
    { method: "DELETE", credentials: "include", cache: "no-store" },
  );
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
}

export async function fetchAgentRunsForProject(
  projectId: string,
  init?: { page?: number; perPage?: number; status?: string; q?: string },
): Promise<ListEnvelope<AgentRunOut>> {
  const p = new URLSearchParams();
  p.set("page", String(init?.page ?? 1));
  p.set("per_page", String(Math.min(init?.perPage ?? 20, API_MAX_PER_PAGE)));
  if (init?.status) {
    p.set("status", init.status);
  }
  if (init?.q) {
    p.set("q", init.q);
  }
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-runs?${p.toString()}`,
    { credentials: "include", cache: "no-store" },
  );
  return parseJsonOrThrow<ListEnvelope<AgentRunOut>>(res);
}

export async function fetchActiveProjectPolicy(
  projectId: string,
): Promise<ActiveGovernancePolicyPayload> {
  return fetchActiveGovernancePolicy(projectId);
}
