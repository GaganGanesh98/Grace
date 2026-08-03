import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

export async function POST(req: Request): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Not authenticated" } }, { status: 401 });
  }
  const url = new URL(req.url);
  const projectId = url.searchParams.get("project_id");
  const qs = new URLSearchParams();
  if (projectId) {
    qs.set("project_id", projectId);
  }
  const backendQs = qs.toString();
  const body = await req.text();
  const cookie = req.headers.get("cookie");
  const r = await fetch(`${getApiUrl()}/v1/governance/verify${backendQs ? `?${backendQs}` : ""}`, {
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
