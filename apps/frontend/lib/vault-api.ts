import { parseApiError } from "@/lib/api";

export type VaultKind = "llm" | "tool" | "custom";

export interface VaultKey {
  id: string;
  user_id: string;
  service: string;
  name: string;
  kind: VaultKind;
  key_prefix: string;
  key_suffix: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DetectResult {
  kind: VaultKind;
  service: string;
}

type VaultKeyWire = Partial<VaultKey> & {
  id: string;
  service: string;
  name: string;
  kind: VaultKind;
  key_prefix: string;
  key_suffix: string;
  created_at: string;
};

async function parseJsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    if (res.status >= 500) {
      throw new Error("Server error, try again.");
    }
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return res.json() as Promise<T>;
}

function normalizeVaultKey(row: VaultKeyWire): VaultKey {
  return {
    id: row.id,
    user_id: row.user_id ?? "",
    service: row.service,
    name: row.name,
    kind: row.kind,
    key_prefix: row.key_prefix,
    key_suffix: row.key_suffix,
    is_active: row.is_active ?? true,
    created_at: row.created_at,
    updated_at: row.updated_at ?? row.created_at,
  };
}

export async function listVaultKeys(filter?: { kind?: VaultKind }): Promise<VaultKey[]> {
  const params = new URLSearchParams();
  if (filter?.kind) {
    params.set("kind", filter.kind);
  }
  const res = await fetch(`/api/vault${params.size ? `?${params.toString()}` : ""}`, {
    credentials: "include",
    cache: "no-store",
  });
  const rows = await parseJsonOrThrow<VaultKeyWire[]>(res);
  return rows.map(normalizeVaultKey);
}

export async function createVaultKey(input: {
  name: string;
  raw_key: string;
  service_override?: string;
  kind_override?: VaultKind;
}): Promise<VaultKey> {
  const res = await fetch("/api/vault", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    cache: "no-store",
  });
  const row = await parseJsonOrThrow<VaultKeyWire>(res);
  return normalizeVaultKey(row);
}

export async function getVaultKey(keyId: string): Promise<VaultKey> {
  const res = await fetch(`/api/vault/${encodeURIComponent(keyId)}`, {
    credentials: "include",
    cache: "no-store",
  });
  const row = await parseJsonOrThrow<VaultKeyWire>(res);
  return normalizeVaultKey(row);
}

export async function updateVaultKey(
  keyId: string,
  input: { name?: string; is_active?: boolean },
): Promise<VaultKey> {
  const res = await fetch(`/api/vault/${encodeURIComponent(keyId)}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    cache: "no-store",
  });
  const row = await parseJsonOrThrow<VaultKeyWire>(res);
  return normalizeVaultKey(row);
}

export async function deleteVaultKey(keyId: string): Promise<void> {
  const res = await fetch(`/api/vault/${encodeURIComponent(keyId)}`, {
    method: "DELETE",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status >= 500) {
      throw new Error("Server error, try again.");
    }
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  await res.text();
}

export async function deactivateVaultKey(keyId: string): Promise<VaultKey> {
  const res = await fetch(`/api/vault/${encodeURIComponent(keyId)}/deactivate`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });
  const row = await parseJsonOrThrow<VaultKeyWire>(res);
  return normalizeVaultKey(row);
}

export async function detectCredential(rawKey: string): Promise<DetectResult> {
  const res = await fetch("/api/vault/detect", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_key: rawKey }),
    cache: "no-store",
  });
  return parseJsonOrThrow<DetectResult>(res);
}
