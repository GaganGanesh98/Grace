import { parseApiError } from "@/lib/api";
import type {
  AgentDefinitionOut,
  AgentRunOut,
  AgentRunWsTokenPayload,
  DataEnvelope,
  ListEnvelope,
} from "@/lib/types";

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

export async function fetchAgentDefinitions(
  projectId: string,
  init?: { page?: number; perPage?: number },
): Promise<AgentDefinitionOut[]> {
  const p = new URLSearchParams();
  p.set("page", String(init?.page ?? 1));
  p.set("per_page", String(init?.perPage ?? 20));
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-definitions?${p.toString()}`,
    {
      credentials: "include",
      cache: "no-store",
    },
  );
  const env = await parseJsonOrThrow<ListEnvelope<AgentDefinitionOut>>(res);
  return env.data;
}

/** All agent definitions (paginated server-side) for batch lookups in Command Center, etc. */
export async function fetchAllAgentDefinitions(projectId: string): Promise<AgentDefinitionOut[]> {
  const per = 100;
  let page = 1;
  const out: AgentDefinitionOut[] = [];
  for (;;) {
    const p = new URLSearchParams();
    p.set("page", String(page));
    p.set("per_page", String(per));
    const res = await fetch(
      `/api/projects/${encodeURIComponent(projectId)}/agent-definitions?${p.toString()}`,
      { credentials: "include", cache: "no-store" },
    );
    const env = await parseJsonOrThrow<ListEnvelope<AgentDefinitionOut>>(res);
    out.push(...env.data);
    const got = env.data.length;
    const total = env.meta.total;
    if (out.length >= total || got < per) {
      return out;
    }
    page += 1;
  }
}

/** Non-archived definition count for a project (from list `meta.total`, minimal payload). */
export async function fetchAgentDefinitionsNonArchivedCount(projectId: string): Promise<number> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-definitions?page=1&per_page=1`,
    { credentials: "include", cache: "no-store" },
  );
  const env = await parseJsonOrThrow<ListEnvelope<AgentDefinitionOut>>(res);
  return env.meta.total;
}

export async function fetchAgentDefinition(
  projectId: string,
  definitionId: string,
): Promise<AgentDefinitionOut> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-definitions/${encodeURIComponent(definitionId)}`,
    { credentials: "include", cache: "no-store" },
  );
  const env = await parseJsonOrThrow<DataEnvelope<AgentDefinitionOut>>(res);
  return env.data;
}

export async function createAgentDefinition(
  projectId: string,
  body: Record<string, unknown>,
): Promise<AgentDefinitionOut> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/agent-definitions`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const env = await parseJsonOrThrow<DataEnvelope<AgentDefinitionOut>>(res);
  return env.data;
}

export async function archiveAgentDefinition(
  projectId: string,
  definitionId: string,
): Promise<AgentDefinitionOut> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-definitions/${encodeURIComponent(definitionId)}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_archived: true }),
      cache: "no-store",
    },
  );
  const env = await parseJsonOrThrow<DataEnvelope<AgentDefinitionOut>>(res);
  return env.data;
}

export async function fetchAgentRuns(projectId: string): Promise<AgentRunOut[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/agent-runs`, {
    credentials: "include",
    cache: "no-store",
  });
  const env = await parseJsonOrThrow<ListEnvelope<AgentRunOut>>(res);
  return env.data;
}

export async function fetchAgentRun(projectId: string, runId: string): Promise<AgentRunOut> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-runs/${encodeURIComponent(runId)}`,
    { credentials: "include", cache: "no-store" },
  );
  const env = await parseJsonOrThrow<DataEnvelope<AgentRunOut>>(res);
  return env.data;
}

export async function createAgentRun(
  projectId: string,
  body: { agent_definition_id: string; input: Record<string, unknown> },
): Promise<AgentRunOut> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/agent-runs`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const env = await parseJsonOrThrow<DataEnvelope<AgentRunOut>>(res);
  return env.data;
}

export async function mintAgentRunWsToken(
  projectId: string,
  runId: string,
): Promise<AgentRunWsTokenPayload> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-runs/${encodeURIComponent(runId)}/ws-token`,
    { method: "POST", credentials: "include", cache: "no-store" },
  );
  const env = await parseJsonOrThrow<DataEnvelope<AgentRunWsTokenPayload>>(res);
  return env.data;
}

export async function cancelAgentRun(projectId: string, runId: string): Promise<AgentRunOut> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/agent-runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST", credentials: "include", cache: "no-store" },
  );
  const env = await parseJsonOrThrow<DataEnvelope<AgentRunOut>>(res);
  return env.data;
}
