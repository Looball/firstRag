import { defineConfig, devices } from "@playwright/test";

const baseURL =
  process.env.FIRSTRAG_E2E_BASE_URL || "http://127.0.0.1:13000";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "full-stack-core.spec.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [
        ["github"],
        ["html", { open: "never", outputFolder: "playwright-report" }],
      ]
    : "line",
  outputDir: "test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
