/**
 * BFF access for command-center aggregate routes (GET /api/command-center/...).
 */

import { parseApiError } from "@/lib/api";
import type { DataEnvelope } from "@/lib/types";
import type { CryptoHealthOut, PolicyBreakdownOut, PostureMetrics, TsaStatusOut } from "@/lib/command-center-types";

export class CommandCenterRequestError extends Error {
  readonly name = "CommandCenterRequestError";

  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function redirectToLoginIfBrowser(): void {
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

async function getJsonWithThrow<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { credentials: "include", cache: "no-store" });
  } catch {
    throw new CommandCenterRequestError("network error", 0);
  }
  if (res.status === 401) {
    redirectToLoginIfBrowser();
    throw new CommandCenterRequestError("Not authenticated", 401);
  }
  if (res.status === 403) {
    const err = await parseApiError(res);
    throw new CommandCenterRequestError(err.message || "Forbidden", 403);
  }
  if (!res.ok) {
    const err = await parseApiError(res);
    throw new CommandCenterRequestError(err.message, res.status);
  }
  const body: unknown = await res.json();
  if (!body || typeof body !== "object" || !("data" in body)) {
    throw new CommandCenterRequestError("Invalid response", res.status);
  }
  return (body as DataEnvelope<T>).data;
}

function qs(projectId: string, extra: Record<string, string>): string {
  const s = new URLSearchParams({ project_id: projectId, ...extra });
  return s.toString();
}

export async function fetchCommandCenterPosture(projectId: string, windowParam = "24h"): Promise<PostureMetrics> {
  return getJsonWithThrow<PostureMetrics>(
    `/api/command-center/posture?${qs(projectId, { window: windowParam })}`,
  );
}

export async function fetchCommandCenterCryptoHealth(projectId: string): Promise<CryptoHealthOut> {
  return getJsonWithThrow<CryptoHealthOut>(`/api/command-center/crypto-health?${qs(projectId, {})}`);
}

export async function fetchCommandCenterPolicyBreakdown(
  projectId: string,
  windowParam = "24h",
): Promise<PolicyBreakdownOut> {
  return getJsonWithThrow<PolicyBreakdownOut>(
    `/api/command-center/policy-breakdown?${qs(projectId, { window: windowParam })}`,
  );
}

export async function fetchCommandCenterTsaStatusOrThrow(projectId: string): Promise<TsaStatusOut> {
  return getJsonWithThrow<TsaStatusOut>(`/api/command-center/tsa-status?${qs(projectId, {})}`);
}
