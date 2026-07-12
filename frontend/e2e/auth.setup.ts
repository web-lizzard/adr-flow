import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test as setup } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, "..", ".auth", "user.json");

const ACCESS_TOKEN_KEY = "adr-flow.access_token";

const email = process.env.E2E_USER_EMAIL ?? "e2e@example.com";
const password = process.env.E2E_USER_PASSWORD ?? "e2e-password-123";

setup("authenticate", async ({ page, request }) => {
  let accessToken: string;

  const registerResponse = await request.post("/api/auth/register", {
    data: { email, password },
  });

  if (registerResponse.ok()) {
    const body = (await registerResponse.json()) as { access_token: string };
    accessToken = body.access_token;
  } else {
    const loginResponse = await request.post("/api/auth/login", {
      data: { email, password },
    });
    expect(loginResponse.ok()).toBeTruthy();
    const body = (await loginResponse.json()) as { access_token: string };
    accessToken = body.access_token;
  }

  await page.goto("/", { waitUntil: "networkidle" });
  await page.sessionStorage.setItem(ACCESS_TOKEN_KEY, accessToken);

  await page.goto("/workspace", { waitUntil: "networkidle" });
  await expect(page).toHaveURL(/\/workspace/);
  await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();

  await mkdir(path.dirname(authFile), { recursive: true });
  await page.context().storageState({ path: authFile });

  const storageState = JSON.parse(await readFile(authFile, "utf8")) as {
    cookies: unknown[];
    origins: Array<{
      origin: string;
      localStorage?: Array<{ name: string; value: string }>;
      sessionStorage?: Array<{ name: string; value: string }>;
    }>;
  };

  const origin =
    storageState.origins.find((entry) => entry.origin.includes("127.0.0.1")) ??
    storageState.origins[0];

  if (origin) {
    origin.sessionStorage = [{ name: ACCESS_TOKEN_KEY, value: accessToken }];
  }

  await writeFile(authFile, `${JSON.stringify(storageState, null, 2)}\n`);
});
