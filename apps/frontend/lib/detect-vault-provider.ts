/** Match backend vault detection prefixes (subset for UI hints). */
export function detectVaultProviderFromKey(key: string): string | null {
  const k = key.trim();
  if (k.startsWith("gsk_")) {
    return "groq";
  }
  if (k.startsWith("sk-ant-")) {
    return "anthropic";
  }
  if (k.startsWith("sk-or-")) {
    return "openai";
  }
  if (k.startsWith("sk-")) {
    return "openai";
  }
  if (k.startsWith("xai-")) {
    return "xai";
  }
  if (k.startsWith("AIza")) {
    return "google";
  }
  if (k.startsWith("r8_")) {
    return "replicate";
  }
  return null;
}
