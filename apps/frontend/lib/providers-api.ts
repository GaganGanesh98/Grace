import { parseApiError } from "@/lib/api";

/** One row of GET /api/v1/providers — a projection of the backend provider registry. */
export interface LlmProvider {
  service: string;
  label: string;
  protocol: string;
  /** Bare model ids as the provider names them upstream (no `provider/` prefix). */
  models: string[];
  /** Preferred model for new agents, or "" when the registry has no curated list. */
  default_model: string;
}

export async function fetchLlmProviders(): Promise<LlmProvider[]> {
  const res = await fetch("/api/providers", { credentials: "include", cache: "no-store" });
  if (!res.ok) {
    if (res.status >= 500) {
      throw new Error("Server error, try again.");
    }
    const err = await parseApiError(res);
    throw new Error(err.message);
  }
  return res.json() as Promise<LlmProvider[]>;
}
