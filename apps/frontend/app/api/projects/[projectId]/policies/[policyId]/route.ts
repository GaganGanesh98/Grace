import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { forwardBackendJson } from "@/lib/bff-forward";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";

type Ctx = { params: Promise<{ projectId: string; policyId: string }> };

export async function GET(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId, policyId } = await context.params;
  const target = `${getApiUrl()}/api/v1/projects/${encodeURIComponent(projectId)}/policies/${encodeURIComponent(policyId)}`;
  return forwardBackendJson(req, token, target, { method: "GET" }, { mapForbiddenToNotFound: true });
}

export async function PATCH(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId, policyId } = await context.params;
  const body = await req.text();
  const target = `${getApiUrl()}/api/v1/projects/${encodeURIComponent(projectId)}/policies/${encodeURIComponent(policyId)}`;
  return forwardBackendJson(
    req,
    token,
    target,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body },
    { mapForbiddenToNotFound: true },
  );
}

export async function DELETE(req: Request, context: Ctx): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { projectId, policyId } = await context.params;
  const target = `${getApiUrl()}/api/v1/projects/${encodeURIComponent(projectId)}/policies/${encodeURIComponent(policyId)}`;
  return forwardBackendJson(req, token, target, { method: "DELETE" }, { mapForbiddenToNotFound: true });
}
