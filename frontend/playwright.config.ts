import { defineConfig, devices } from "@playwright/test";

const E2E_PORT = 3100;
const E2E_ORIGIN = `http://127.0.0.1:${E2E_PORT}`;

/** 在独立 Next.js dev server 中运行不依赖后端的浏览器回归。 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [
        ["github"],
        ["html", { open: "never", outputFolder: "playwright-report" }],
      ]
    : "line",
  outputDir: "test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: E2E_ORIGIN,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npm run dev -- --hostname 127.0.0.1 --port ${E2E_PORT}`,
    env: {
      NEXT_TELEMETRY_DISABLED: "1",
    },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    url: E2E_ORIGIN,
  },
});
