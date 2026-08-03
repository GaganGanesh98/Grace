import { cookies } from "next/headers";
import { type NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { forwardBackendJson } from "@/lib/bff-forward";
import { getApiUrl } from "@/lib/env";

type RouteContext = { params: Promise<{ keyId: string }> };

export async function GET(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { keyId } = await context.params;
  return forwardBackendJson(req, token, `${getApiUrl()}/api/v1/vault/${encodeURIComponent(keyId)}`);
}

export async function PATCH(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { keyId } = await context.params;
  const body = await req.text();
  return forwardBackendJson(req, token, `${getApiUrl()}/api/v1/vault/${encodeURIComponent(keyId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body,
  });
}

export async function DELETE(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { keyId } = await context.params;
  return forwardBackendJson(req, token, `${getApiUrl()}/api/v1/vault/${encodeURIComponent(keyId)}`, {
    method: "DELETE",
  });
}
