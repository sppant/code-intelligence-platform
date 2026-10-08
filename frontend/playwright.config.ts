import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests exercise the REAL stack end-to-end (frontend + backend +
 * Postgres + a real GitHub clone for the analyze step) -- there is no
 * mocking layer. The backend (`uv run uvicorn backend.main:app --port
 * 8000`) and a local Postgres with migrations applied must already be
 * running before this suite is run; see README's "Testing" section.
 *
 * Only the frontend dev server is started here (and only if one isn't
 * already running on :5173) since Playwright's webServer option manages a
 * single process, not a multi-service stack.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 30_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
