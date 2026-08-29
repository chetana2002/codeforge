import { defineConfig, devices } from "@playwright/test";

// Runs against the actual docker-compose stack rather than spinning up its own
// server: the flow under test spans the frontend, API, Redis Streams, and a
// real Docker sandbox container, which isn't something Playwright's webServer
// directive (built for a single process) can stand up on its own. Start the
// stack first with `docker compose up -d --build` from the repo root.
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
