import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";
import { jsonError } from "@/lib/http-errors";

type RouteContext = { params: Promise<{ projectId: string }> };

export async function GET(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return jsonError("unauthorized", "Not authenticated", 401);
  }
  const { projectId } = await context.params;
  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const target = `${getApiUrl()}/api/v1/projects/${encodeURIComponent(projectId)}/api-keys${qs ? `?${qs}` : ""}`;
  const cookie = req.headers.get("cookie");
  const r = await fetch(target, {
    headers: {
      Authorization: `Bearer ${token}`,
      ...(cookie ? { Cookie: cookie } : {}),
    },
    credentials: "include",
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}

export async function POST(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return jsonError("unauthorized", "Not authenticated", 401);
  }
  const { projectId } = await context.params;
  const body = await req.text();
  const cookie = req.headers.get("cookie");
  const r = await fetch(`${getApiUrl()}/api/v1/projects/${encodeURIComponent(projectId)}/api-keys`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body,
    credentials: "include",
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}
