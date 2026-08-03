import { expect, test } from "@playwright/test";

test("login page renders", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("AXIOM", { exact: true })).toBeVisible();
});

test("redirect to login when unauthenticated", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

test("health check", async ({ request }) => {
  const base = (process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const res = await request.get(`${base}/healthz`);
  expect(res.status()).toBe(200);
});
