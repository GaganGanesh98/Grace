import { expect, test } from "@playwright/test";

const GROQ_KEY = process.env.GROQ_SMOKE_KEY?.trim();

test.describe.configure({ timeout: 600_000 });

test("agent runner smoke: vault → definition → run (Groq)", async ({ page }) => {
  test.skip(!GROQ_KEY, "Set GROQ_SMOKE_KEY to a gsk_… key for this test.");

  const stamp = Date.now();
  const email = `smoke.${stamp}@example.com`;
  const password = "password1a";

  await page.goto("/signup");
  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel(/^Password$/i).fill(password);
  await page.getByRole("button", { name: "Sign up", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 60_000 });

  const res = await page.request.post("/api/projects", {
    data: JSON.stringify({ name: `Smoke Project ${stamp}`, description: "e2e" }),
    headers: { "Content-Type": "application/json" },
  });
  expect(res.ok()).toBeTruthy();
  const projJson = (await res.json()) as { data: { id: string } };
  const projectId = projJson.data.id;

  await page.goto("/dashboard/vault");
  await page.getByRole("button", { name: /add credential/i }).click();
  await page.getByLabel(/NAME/i).fill("groq-smoke");
  await page.getByLabel(/CREDENTIAL/i).fill(GROQ_KEY!);
  await page.getByRole("button", { name: /^add credential$/i }).click();
  await expect(page.getByText(/groq/i)).toBeVisible({ timeout: 30_000 });

  await page.goto(`/dashboard/projects/${projectId}/agent-definitions`);
  const defForm = page.locator("form").filter({
    has: page.getByRole("button", { name: /create agent/i }),
  });
  await expect(defForm.locator("select option")).not.toHaveCount(0, { timeout: 60_000 });
  await defForm.getByRole("textbox").nth(0).fill("Smoke Test Agent");
  await defForm.getByRole("textbox").nth(1).fill("groq/llama-3.3-70b-versatile");
  await defForm.getByRole("textbox").nth(2).fill("You are a helpful assistant.");
  const createRespPromise = page.waitForResponse(
    (r) =>
      r.url().includes("/api/projects/") &&
      r.url().includes("/agent-definitions") &&
      r.request().method() === "POST" &&
      !r.url().includes("/agent-definitions/"),
  );
  await defForm.getByRole("button", { name: /create agent/i }).click();
  const createResp = await createRespPromise;
  if (!createResp.ok()) {
    throw new Error(`Create agent failed: ${createResp.status()} ${await createResp.text()}`);
  }
  await page.reload();
  await expect(page.getByRole("link", { name: /Smoke Test Agent/i })).toBeVisible({ timeout: 60_000 });

  await page.getByRole("link", { name: /Smoke Test Agent/i }).first().click();
  await expect(page).toHaveURL(/\/agent-definitions\//);
  await page.getByRole("button", { name: /^run$/i }).click();
  await page.getByPlaceholder(/What should the agent do/i).fill(
    "Reply with exactly: OK_SMOKE_DONE",
  );
  await Promise.all([
    page.waitForURL(/\/runs\//, { timeout: 120_000 }),
    page.getByTestId("start-agent-run").click(),
  ]);

  await expect(page.getByText(/Live execution|Run in progress|Status:/i).first()).toBeVisible({
    timeout: 120_000,
  });

  await expect(page.locator("p").filter({ hasText: /^Status:/ })).toBeVisible({ timeout: 30_000 });

  // Full terminal completion requires the worker, Redis, gateway on :8001, and
  // `AXIOM_WORKER_GATEWAY_API_KEY`. Set SMOKE_REQUIRE_TERMINAL=1 to assert succeeded|failed|cancelled.
  if (process.env.SMOKE_REQUIRE_TERMINAL === "1") {
    const terminal = page.locator("text=/succeeded|failed|cancelled/i");
    await expect(terminal.first()).toBeVisible({ timeout: 480_000 });
  }
});
