import { expect, test } from "@playwright/test";

const RUN_INTEGRATION = Boolean(process.env.E2E_COMMAND_CENTER_DRAWER?.trim());

/**
 * Full drawer flows need: signed-in user, active project, and governance rows on Command Center.
 * Set E2E_COMMAND_CENTER_DRAWER=1 when the dev stack has seeded activity.
 */

test("login page body uses readable font sizes (baseline for typography regression)", async ({
  page,
}) => {
  await page.goto("/login");
  const fs = await page.locator("body").evaluate((el) => getComputedStyle(el).fontSize);
  const n = parseFloat(fs);
  expect(n).toBeGreaterThanOrEqual(10);
  expect(n).toBeLessThanOrEqual(20);
});

test("row click opens governance receipt drawer (integration)", async ({ page }) => {
  test.skip(!RUN_INTEGRATION, "Set E2E_COMMAND_CENTER_DRAWER=1 with dev stack + ledger rows.");
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: /command center/i })).toBeVisible({
    timeout: 60_000,
  });
  const row = page.locator("[data-receipt-row]").first();
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.click();
  await expect(page.getByRole("dialog", { name: /governance receipt/i })).toBeVisible();
  await expect(page.getByText(/signatures/i)).toBeVisible();
});

test("Escape closes drawer (integration)", async ({ page }) => {
  test.skip(!RUN_INTEGRATION, "Set E2E_COMMAND_CENTER_DRAWER=1 with dev stack + ledger rows.");
  await page.goto("/dashboard");
  await page.locator("[data-receipt-row]").first().click({ timeout: 60_000 });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: /governance receipt/i })).toHaveCount(0);
});

test("backdrop click closes drawer (integration)", async ({ page }) => {
  test.skip(!RUN_INTEGRATION, "Set E2E_COMMAND_CENTER_DRAWER=1 with dev stack + ledger rows.");
  await page.goto("/dashboard");
  await page.locator("[data-receipt-row]").first().click({ timeout: 60_000 });
  await page.getByRole("button", { name: "Close drawer" }).click();
  await expect(page.getByRole("dialog", { name: /governance receipt/i })).toHaveCount(0);
});
