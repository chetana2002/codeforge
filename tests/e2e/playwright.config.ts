import { defineConfig, devices } from "@playwright/test";

// Runs against the real docker-compose stack — start it first with
// `docker compose up -d --build` from the repo root.
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3002";

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
