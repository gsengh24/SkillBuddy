import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against a running stack (CI job "Smoke": docker compose + Mailpit),
 * run inside the official Playwright image (browsers preinstalled).
 * Elsewhere: start the stack, then `npm ci && npx playwright install chromium && npm test` here.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
