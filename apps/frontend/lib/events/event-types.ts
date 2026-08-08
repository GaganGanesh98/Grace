/**
 * Server envelope for project-scoped events (GET /v1/events/stream, BFF /api/events/stream).
 */
export type GraceEvent = {
  type: string;
  project_id: string;
  ts: string;
  payload: Record<string, unknown>;
};

export type GraceEventsStatus = "connecting" | "connected" | "disconnected" | "reconnecting";
