import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

type Ctx = { params: Promise<{ projectId: string; runId: string; filename: string }> };

export async function GET(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Not authenticated" } }, { status: 401 });
  }
  const { projectId, runId, filename } = await context.params;
  const enc = encodeURIComponent(filename);
  const target = `${getApiUrl()}/v1/agent-runs/${encodeURIComponent(runId)}/artifacts/${enc}?project_id=${encodeURIComponent(projectId)}`;
  const cookie = req.headers.get("cookie");
  const r = await fetch(target, {
    headers: {
      Authorization: `Bearer ${token}`,
      ...(cookie ? { Cookie: cookie } : {}),
    },
    credentials: "include",
    cache: "no-store",
  });
  if (r.status === 401) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  const buf = await r.arrayBuffer();
  const headers = new Headers();
  const ct = r.headers.get("content-type");
  const cd = r.headers.get("content-disposition");
  if (ct) {
    headers.set("content-type", ct);
  }
  if (cd) {
    headers.set("content-disposition", cd);
  }
  return new NextResponse(buf, { status: r.status, headers });
}
