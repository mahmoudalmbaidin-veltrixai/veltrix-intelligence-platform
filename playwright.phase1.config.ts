import { defineConfig } from '@playwright/test'
import baseConfig from './playwright.config'

// Focused cross-browser certification config. The platform-wide secret scanner
// remains part of the full suite; this bounded run avoids rescanning unrelated
// historical traces after each Phase 1 verification iteration.
export default defineConfig({
  ...baseConfig,
  globalTeardown: undefined,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-phase1', open: 'never' }]],
  outputDir: 'test-results-phase1',
  projects: baseConfig.projects?.filter((project) =>
    ['chrome-desktop', 'firefox-desktop', 'webkit-desktop'].includes(project.name ?? ''),
  ),
})
