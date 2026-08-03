import type { ApiErrorBody, DataEnvelope, ListEnvelope, ProjectOut, UserPublic } from "@/lib/types";

export type ParsedApiError = {
  code: string;
  message: string;
};

export async function parseApiError(res: Response): Promise<ParsedApiError> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "error" in body) {
      const err = (body as ApiErrorBody).error;
      return {
        code: typeof err.code === "string" ? err.code : "error",
        message: typeof err.message === "string" ? err.message : "Request failed",
      };
    }
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail?: unknown }).detail;
      const message =
        typeof d === "string"
          ? d
          : d && typeof d === "object" && "message" in d && typeof (d as { message?: unknown }).message === "string"
            ? String((d as { message: string }).message)
            : "Request failed";
      return { code: "error", message };
    }
  } catch {
    /* ignore malformed JSON */
  }
  return { code: "error", message: "Request failed" };
}

async function parseJson<T>(res: Response): Promise<T> {
  const body: unknown = await res.json();
  return body as T;
}

export async function apiLogin(email: string, password: string): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
}

export async function apiSignup(
  email: string,
  password: string,
  fullName?: string,
): Promise<void> {
  const res = await fetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
}

export async function apiGoogleCallback(code: string, state: string): Promise<void> {
  const res = await fetch("/api/auth/google/callback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, state }),
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
}

/** Opens Google OAuth in the same window (BFF sets cookies on callback). */
export function startGoogleOAuth(): void {
  window.location.assign("/api/auth/google");
}

export async function apiLogout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

export async function apiListProjects(): Promise<ListEnvelope<ProjectOut>> {
  const res = await fetch("/api/projects", { method: "GET", credentials: "include" });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return parseJson<ListEnvelope<ProjectOut>>(res);
}

export async function apiCreateProject(name: string, description?: string): Promise<ProjectOut> {
  const res = await fetch("/api/projects", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  const envelope = await parseJson<DataEnvelope<ProjectOut>>(res);
  return envelope.data;
}

export async function apiMe(): Promise<UserPublic> {
  const res = await fetch("/api/me", { method: "GET" });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  const envelope = await parseJson<DataEnvelope<UserPublic>>(res);
  return envelope.data;
}

/** API key row from BFF; backend may include revoked keys — filter with `!revoked_at` for active keys. */
export type ProjectApiKeyRow = {
  id: string;
  project_id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  revoked_at?: string | null;
};

type ListKeysJson = {
  data: (ProjectApiKeyRow & { api_key_id?: string })[];
  meta: { total: number; page: number; per_page: number; has_more: boolean };
};

function normalizeApiKeyId(row: ProjectApiKeyRow & { api_key_id?: string }): string {
  const raw = row.id ?? row.api_key_id;
  return raw != null ? String(raw) : "";
}

/** Lists keys and drops revoked rows (revoked_at set). */
export async function apiListProjectKeys(projectId: string): Promise<ProjectApiKeyRow[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/api-keys`, {
    credentials: "include",
  });
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  const json = (await res.json()) as ListKeysJson;
  return json.data
    .map((row) => ({
      ...row,
      id: normalizeApiKeyId(row),
    }))
    .filter((k) => !k.revoked_at);
}

export async function apiRevokeApiKey(projectId: string, keyId: string): Promise<void> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/api-keys/${encodeURIComponent(keyId)}`,
    { method: "DELETE", credentials: "include" },
  );
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
}
