import { defineConfig, devices } from '@playwright/test';

// Not the dev ports: a dev API may have live mode on, and E2E must only ever see replay.
const WEB_PORT = 5174;
const API_PORT = 8765;
const isCi = Boolean(process.env.CI);

/**
 * E2E runs the real app against the real API in replay mode: no keys, no live calls, no spend.
 * Chromium runs everything; Firefox and WebKit run the journey and the axe scan.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: isCi,
  retries: isCi ? 1 : 0,
  reporter: isCi ? [['list'], ['html', { open: 'never' }]] : 'list',
  // Baselines are per OS (fonts render differently), so each platform keeps its own.
  snapshotPathTemplate: '{testDir}/__screenshots__/{platform}/{testFilePath}/{arg}{ext}',
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: 'disabled' } },
  use: {
    baseURL: `http://localhost:${String(WEB_PORT)}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      testMatch: /(journey|a11y)\.spec\.ts/,
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      testMatch: /(journey|a11y)\.spec\.ts/,
    },
  ],
  webServer: [
    {
      // Replay only: LIVE_ENABLED is forced off and no keys reach the server.
      command: `uv run --frozen uvicorn jev.api.app:create_app --factory --port ${String(API_PORT)}`,
      cwd: '..',
      url: `http://127.0.0.1:${String(API_PORT)}/api/scenarios`,
      env: { LIVE_ENABLED: 'false', TYPESAFE_API_KEY: '', OPENAI_API_KEY: '' },
      reuseExistingServer: !isCi,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --port ${String(WEB_PORT)} --strictPort`,
      url: `http://localhost:${String(WEB_PORT)}`,
      env: { JEV_API_TARGET: `http://127.0.0.1:${String(API_PORT)}` },
      reuseExistingServer: !isCi,
      timeout: 60_000,
    },
  ],
});
