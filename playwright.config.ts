import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  globalTeardown: './tests/e2e/global-teardown.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  // Live control-plane and connection tests intentionally share a seeded tenant.
  // Serial execution keeps session/rate-limit state deterministic across personas.
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3009',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chrome-desktop', use: { ...devices['Desktop Chrome'], browserName: 'chromium' } },
    { name: 'edge-desktop', use: { ...devices['Desktop Chrome'], channel: 'msedge' } },
    { name: 'firefox-desktop', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit-desktop', use: { ...devices['Desktop Safari'], browserName: 'webkit' } },
    {
      name: 'chrome-high-dpi',
      grep: /@a11y|@mobile/,
      use: { ...devices['Desktop Chrome'], browserName: 'chromium', deviceScaleFactor: 2 },
    },
    {
      name: 'chromium-mobile',
      grep: /@mobile/,
      use: { ...devices['iPhone 13'], browserName: 'chromium', viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command: 'npm run build && npm run preview',
    url: 'http://localhost:3009',
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === '1',
    timeout: 120_000,
    env: {
      VITE_API_MODE: 'live',
      VITE_APP_ENV: 'production',
      VITE_ENABLE_MOCK_LATENCY: 'false',
      VITE_API_BASE_URL: 'http://localhost:8000/api/v1',
    },
  },
})
