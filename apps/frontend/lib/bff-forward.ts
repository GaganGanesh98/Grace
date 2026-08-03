import { NextResponse } from "next/server";

import { jsonError } from "@/lib/http-errors";

type ForwardOpts = {
  /** Map backend 403 (membership / wrong project) to 404 for existence hiding. */
  mapForbiddenToNotFound?: boolean;
};

/** Forward an authenticated request to the FastAPI backend; 401 → redirect to login. */
export async function forwardBackendJson(
  req: Request,
  token: string | undefined,
  targetUrl: string,
  init: RequestInit & { method?: string } = {},
  opts: ForwardOpts = {},
): Promise<NextResponse> {
  if (!token) {
    return jsonError("unauthorized", "Not authenticated", 401);
  }
  const cookie = req.headers.get("cookie");
  const r = await fetch(targetUrl, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(cookie ? { Cookie: cookie } : {}),
      ...(init.headers ?? {}),
    },
    credentials: "include",
    cache: "no-store",
  });
  if (r.status === 401) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  if (opts.mapForbiddenToNotFound && r.status === 403) {
    return jsonError("not_found", "Not found", 404);
  }
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") ?? "application/json" },
  });
}
