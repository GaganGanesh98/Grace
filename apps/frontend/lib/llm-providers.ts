/**
 * LLM services an agent definition can be created against.
 *
 * The gateway's provider registry
 * (`apps/backend/src/axiom/gateway/provider_registry.py`) knows more providers
 * than this — this is the narrower set the agent creation flow accepts. Kept in
 * one place so the check is not buried inside a submit handler.
 */
export const SUPPORTED_LLM_SERVICES = ["openai", "anthropic", "google", "groq", "xai"] as const;

export type SupportedLlmService = (typeof SUPPORTED_LLM_SERVICES)[number];

/** Human-readable list used in validation copy. */
export const SUPPORTED_LLM_SERVICES_LABEL = "OpenAI, Anthropic, Google, Groq, or xAI";

export function isSupportedLlmService(service: string): boolean {
  return (SUPPORTED_LLM_SERVICES as readonly string[]).includes(service.trim().toLowerCase());
}

/** Subset of vault keys an agent definition can actually be created against. */
export function supportedLlmKeys<T extends { service: string }>(keys: readonly T[]): T[] {
  return keys.filter((k) => isSupportedLlmService(k.service));
}

/** Field error shown when the selected credential is not an LLM provider key we run agents on. */
export function unsupportedServiceMessage(name: string, service: string): string {
  return `"${name}" is a ${service} credential. Agents need an LLM provider key — ${SUPPORTED_LLM_SERVICES_LABEL}.`;
}

/**
 * Agent definitions store models as `provider/model`; the gateway strips the
 * prefix before calling upstream (`normalize_model_prefix`).
 */
export function qualifyModel(service: string, model: string): string {
  return `${service}/${model}`;
}

/** Provider named by a `provider/model` string, or null when the id is bare. */
export function modelProviderPrefix(model: string): string | null {
  const i = model.indexOf("/");
  if (i <= 0 || i === model.length - 1) {
    return null;
  }
  return model.slice(0, i).trim().toLowerCase();
}

/** Field error for a model whose provider prefix contradicts the selected credential. */
export function modelProviderMismatchMessage(model: string, prefix: string, service: string): string {
  return `"${model}" is a ${prefix} model, but the selected credential is a ${service} key. This fails at run time, not here.`;
}
