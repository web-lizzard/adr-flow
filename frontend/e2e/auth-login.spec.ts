import { expect, test } from "@playwright/test";

const email = process.env.E2E_USER_EMAIL ?? "e2e@example.com";
const password = process.env.E2E_USER_PASSWORD ?? "e2e-password-123";

// Risk anchor: context/foundation/test-plan.md §1 North star (auth E2E required)
// Provenance: context/foundation/test-plan.md §3 Phase 3
test.use({ storageState: { cookies: [], origins: [] } });

test("auth login routes user to workspace", async ({ page }) => {
  // Step 1-2: Navigate to login and confirm sign-in form renders.
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.waitForLoadState("networkidle");

  // Step 3-5: Sign in with the seeded E2E credentials.
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/workspace/, { timeout: 15_000 }),
    page.getByRole("button", { name: "Sign in" }).click(),
  ]);

  // Step 6-7: Successful login lands on workspace.
  await expect(page).toHaveURL(/\/workspace/);
  await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
});
