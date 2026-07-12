import { defineConfig, devices } from "@playwright/test";

const authFile = ".auth/user.json";
const backendURL = "http://127.0.0.1:8100";
const frontendURL = "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "list" : "html",
  use: {
    baseURL: frontendURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: authFile,
      },
      dependencies: ["setup"],
    },
  ],
  webServer: [
    {
      command:
        "cd ../backend && LLM_PROVIDER=fake uv run uvicorn main:app --port 8100 --no-access-log",
      url: `${backendURL}/docs`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command:
        "NUXT_API_UPSTREAM=http://127.0.0.1:8100 pnpm run dev --host 127.0.0.1 --port 3100",
      url: frontendURL,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
