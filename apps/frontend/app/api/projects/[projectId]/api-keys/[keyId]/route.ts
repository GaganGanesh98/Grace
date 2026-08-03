import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";
import { getApiUrl } from "@/lib/env";
import { jsonError } from "@/lib/http-errors";

type RouteContext = { params: Promise<{ projectId: string; keyId: string }> };

export async function DELETE(req: Request, context: RouteContext): Promise<NextResponse> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) {
    return jsonError("unauthorized", "Not authenticated", 401);
  }
  const { projectId, keyId } = await context.params;
  const cookie = req.headers.get("cookie");
  const r = await fetch(
    `${getApiUrl()}/api/v1/projects/${encodeURIComponent(projectId)}/api-keys/${encodeURIComponent(keyId)}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(cookie ? { Cookie: cookie } : {}),
      },
      credentials: "include",
      cache: "no-store",
    },
  );
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}
