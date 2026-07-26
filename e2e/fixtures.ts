import { test as base, expect, type Page } from '@playwright/test'

export const E2E_EMAIL = process.env.VIP_E2E_EMAIL ?? ''
export const E2E_PASSWORD = process.env.VIP_E2E_PASSWORD ?? ''

async function resetClientState(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem('vip.e2e.initialized')) return
    localStorage.clear()
    sessionStorage.clear()
    sessionStorage.setItem('vip.e2e.initialized', '1')
  })
}

export async function signInAs(page: Page, email: string, password: string) {
  if (!email || !password) throw new Error('E2E email and password are required')
  await page.goto('/login')
  await page.getByLabel('Work email').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/home$/)
}

async function signIn(page: Page) {
  await signInAs(page, E2E_EMAIL, E2E_PASSWORD)
}

export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ page }, use) => {
    // Every authenticated fixture starts from a provably empty browser session.
    // This also protects fully-parallel suites that are constrained to one
    // worker from inheriting a session after a failed test teardown.
    await page.context().clearCookies()
    await resetClientState(page)
    await signIn(page)
    await expect(page.locator('#vip-main')).toBeVisible()
    await use(page)
  },
})

export { expect, resetClientState, signIn }
