import { cookies } from "next/headers";
import { type NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { forwardBackendJson } from "@/lib/bff-forward";
import { getApiUrl } from "@/lib/env";

type RouteContext = { params: Promise<{ keyId: string }> };

export async function POST(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const { keyId } = await context.params;
  return forwardBackendJson(
    req,
    token,
    `${getApiUrl()}/api/v1/vault/${encodeURIComponent(keyId)}/deactivate`,
    { method: "POST" },
  );
}
