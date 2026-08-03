/** Browser-visible API base (HTTP). WebSocket uses ws/wss from the same host. */
export function getPublicApiUrl(): string {
  const u = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (u) {
    return u.replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.location.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

export function getAgentRunWebSocketUrl(runId: string, token: string): string {
  const http = getPublicApiUrl();
  const ws =
    http.startsWith("https://") ? `wss://${http.slice("https://".length)}` : `ws://${http.slice("http://".length)}`;
  const u = new URL(`${ws}/ws/agent-runs/${encodeURIComponent(runId)}`);
  u.searchParams.set("token", token);
  return u.toString();
}
