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

/** Field error shown when the selected credential is not an LLM provider key we run agents on. */
export function unsupportedServiceMessage(name: string, service: string): string {
  return `"${name}" is a ${service} credential. Agents need an LLM provider key — ${SUPPORTED_LLM_SERVICES_LABEL}.`;
}
