import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";

export function middleware(request: NextRequest): NextResponse {
  const path = request.nextUrl.pathname;
  const token = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;

  if (path.startsWith("/dashboard")) {
    if (!token) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
    return NextResponse.next();
  }

  if (path === "/login" || path === "/signup") {
    // Do not redirect to /dashboard just because a cookie exists: the token may be
    // expired or invalid, and /dashboard will send users here on 401 — redirecting
    // back would create an infinite 307 loop.
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/signup"],
};
