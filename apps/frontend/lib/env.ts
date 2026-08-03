/** Server-side base URL for the FastAPI backend (no trailing slash). */
export function getApiUrl(): string {
  const url = process.env.API_URL?.trim();
  if (!url) {
    // `next build` sets NODE_ENV=production while prerendering; do not require API_URL at compile time.
    const isNextCompile =
      process.env.npm_lifecycle_event === "build" ||
      (process.argv.some((a) => a.includes("next")) && process.argv.includes("build"));
    if (process.env.NODE_ENV === "production" && !isNextCompile) {
      throw new Error(
        "API_URL environment variable is required in production. " +
          "Set it to your backend URL (e.g., https://api.axiom.dev)",
      );
    }
    return "http://127.0.0.1:8000";
  }
  return url.replace(/\/$/, "");
}
