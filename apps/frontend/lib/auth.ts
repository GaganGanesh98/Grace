/**
 * Access and refresh JWTs are issued by FastAPI but stored only in httpOnly cookies
 * set by Next.js Route Handlers under `app/api/auth/*`. Client JavaScript never reads tokens.
 */
export { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/auth-cookies";
