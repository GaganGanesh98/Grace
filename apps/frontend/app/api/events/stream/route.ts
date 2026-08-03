import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * BFF: proxy backend SSE to the browser (EventSource is same-origin, cookies,
 * and cannot set Authorization; we forward the access token to the API).
 */
export async function GET(req: Request): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "Not authenticated" } },
      { status: 401 },
    );
  }
  const url = new URL(req.url);
  const projectId = url.searchParams.get("project_id");
  if (!projectId) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "project_id is required" } },
      { status: 400 },
    );
  }
  const target = new URL(
    `${getApiUrl()}/v1/events/stream?project_id=${encodeURIComponent(projectId)}`,
  );
  const r = await fetch(target.toString(), {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return new NextResponse(r.body, {
    status: r.status,
    headers: {
      "content-type": r.headers.get("content-type") ?? "text/event-stream",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    },
  });
}
