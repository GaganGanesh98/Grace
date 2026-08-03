import { cookies } from "next/headers";
import { type NextResponse } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { forwardBackendJson } from "@/lib/bff-forward";
import { getApiUrl } from "@/lib/env";

export async function POST(req: Request): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  const body = await req.text();
  return forwardBackendJson(req, token, `${getApiUrl()}/api/v1/vault/detect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}
