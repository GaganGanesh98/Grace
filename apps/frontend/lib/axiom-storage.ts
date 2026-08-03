export const FONT_SCALE_LS_KEY = "axiom-font-scale";
/** Legacy single key; migrated to per-project slot on read */
export const GOVERNANCE_API_KEY_LS_KEY = "axiom-governance-api-key";
export const ACTIVE_PROJECT_ID_LS_KEY = "axiom-active-project-id";

export const GOVERNANCE_API_KEY_STORAGE_PREFIX = "axiom-governance-api-key-";

export type FontScaleValue = 0.85 | 1.0 | 1.15 | 1.3;

export const FONT_SCALE_OPTIONS: { value: FontScaleValue; label: string }[] = [
  { value: 0.85, label: "Compact" },
  { value: 1.0, label: "Default" },
  { value: 1.15, label: "Large" },
  { value: 1.3, label: "Extra large" },
];

export function governanceApiKeyStorageKey(projectId: string): string {
  return `${GOVERNANCE_API_KEY_STORAGE_PREFIX}${projectId}`;
}

export function writeGovernanceApiKeyForProject(projectId: string, fullKey: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(governanceApiKeyStorageKey(projectId), fullKey);
}

function readValidatedKey(raw: string | null | undefined): string | null {
  const v = raw?.trim();
  return v && v.startsWith("axm_") ? v : null;
}

/** Reads the governance API key for the active project (from localStorage), with legacy migration. */
export function readGovernanceApiKey(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const pid = window.localStorage.getItem(ACTIVE_PROJECT_ID_LS_KEY)?.trim();
  if (pid) {
    const scoped = readValidatedKey(window.localStorage.getItem(governanceApiKeyStorageKey(pid)));
    if (scoped) {
      return scoped;
    }
    const legacy = readValidatedKey(window.localStorage.getItem(GOVERNANCE_API_KEY_LS_KEY));
    if (legacy) {
      try {
        window.localStorage.setItem(governanceApiKeyStorageKey(pid), legacy);
      } catch {
        /* ignore */
      }
      return legacy;
    }
    return null;
  }
  return readValidatedKey(window.localStorage.getItem(GOVERNANCE_API_KEY_LS_KEY));
}

export function readFontScaleFromStorage(): FontScaleValue {
  if (typeof window === "undefined") {
    return 1.0;
  }
  const raw = window.localStorage.getItem(FONT_SCALE_LS_KEY);
  const n = raw ? Number(raw) : 1;
  if (n === 0.85 || n === 1.15 || n === 1.3) {
    return n;
  }
  return 1.0;
}
