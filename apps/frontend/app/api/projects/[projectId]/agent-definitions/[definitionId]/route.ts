import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { forwardBackendJson } from "@/lib/bff-forward";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

type Ctx = { params: Promise<{ projectId: string; definitionId: string }> };

export async function GET(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId, definitionId } = await context.params;
  const target = `${getApiUrl()}/v1/agent-definitions/${encodeURIComponent(definitionId)}?project_id=${encodeURIComponent(projectId)}`;
  return forwardBackendJson(req, token, target, { method: "GET" }, { mapForbiddenToNotFound: true });
}

export async function PATCH(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId, definitionId } = await context.params;
  const body = await req.text();
  const target = `${getApiUrl()}/v1/agent-definitions/${encodeURIComponent(definitionId)}?project_id=${encodeURIComponent(projectId)}`;
  return forwardBackendJson(
    req,
    token,
    target,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body,
    },
    { mapForbiddenToNotFound: true },
  );
}
