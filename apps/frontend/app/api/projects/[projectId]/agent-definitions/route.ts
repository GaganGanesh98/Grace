import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { forwardBackendJson } from "@/lib/bff-forward";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

type Ctx = { params: Promise<{ projectId: string }> };

export async function GET(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId } = await context.params;
  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const target = `${getApiUrl()}/v1/agent-definitions?project_id=${encodeURIComponent(projectId)}${qs ? `&${qs}` : ""}`;
  return forwardBackendJson(req, token, target, { method: "GET" }, { mapForbiddenToNotFound: true });
}

export async function POST(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId } = await context.params;
  const body = await req.text();
  const target = `${getApiUrl()}/v1/agent-definitions?project_id=${encodeURIComponent(projectId)}`;
  return forwardBackendJson(
    req,
    token,
    target,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    },
    { mapForbiddenToNotFound: true },
  );
}
