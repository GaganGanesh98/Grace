import { NextResponse } from "next/server";

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

const ACCESS_MAX_AGE_SECONDS = 60 * 60;
const REFRESH_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;

function secureFlag(): boolean {
  const v = process.env.AXIOM_COOKIE_SECURE?.trim().toLowerCase();
  if (v === "true") {
    return true;
  }
  if (v === "false") {
    return false;
  }
  return process.env.NODE_ENV === "production";
}

function sameSite(): "lax" | "strict" | "none" {
  const raw = process.env.AXIOM_COOKIE_SAMESITE?.trim().toLowerCase();
  if (raw === "strict" || raw === "none" || raw === "lax") {
    return raw;
  }
  return "lax";
}

function baseCookieOpts(): {
  httpOnly: boolean;
  sameSite: "lax" | "strict" | "none";
  path: string;
  secure: boolean;
  domain?: string;
} {
  const domain = process.env.AXIOM_COOKIE_DOMAIN?.trim();
  const opts: {
    httpOnly: boolean;
    sameSite: "lax" | "strict" | "none";
    path: string;
    secure: boolean;
    domain?: string;
  } = { httpOnly: true, sameSite: sameSite(), path: "/", secure: secureFlag() };
  if (domain) {
    opts.domain = domain;
  }
  return opts;
}

export function setAuthCookies(res: NextResponse, access: string, refresh: string): void {
  const opts = baseCookieOpts();
  res.cookies.set(ACCESS_TOKEN_COOKIE, access, { ...opts, maxAge: ACCESS_MAX_AGE_SECONDS });
  res.cookies.set(REFRESH_TOKEN_COOKIE, refresh, { ...opts, maxAge: REFRESH_MAX_AGE_SECONDS });
}

export function clearAuthCookies(res: NextResponse): void {
  const opts = baseCookieOpts();
  res.cookies.set(ACCESS_TOKEN_COOKIE, "", { ...opts, maxAge: 0 });
  res.cookies.set(REFRESH_TOKEN_COOKIE, "", { ...opts, maxAge: 0 });
}
