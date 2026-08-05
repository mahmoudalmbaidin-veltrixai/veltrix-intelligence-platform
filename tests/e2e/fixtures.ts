import { test as base, expect, type Page } from '@playwright/test'
import { browserFixtures } from './personas'

export const E2E_EMAIL = browserFixtures.primary.email
export const E2E_PASSWORD = browserFixtures.primary.password
export const E2E_ORGANIZATION_NAME = browserFixtures.organizationA

async function resetClientState(page: Page) {
  await page.context().clearCookies()
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
  await page.getByLabel('Username or email').fill(email)
  await page.locator('input[name="password"]').fill(password)
  const loginResponse = page.waitForResponse(
    (response) => response.request().method() === 'POST' && response.url().endsWith('/auth/login'),
  )
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  expect((await loginResponse).status()).toBe(200)
  await expect(page).toHaveURL(/\/home$/, { timeout: 20_000 })
}

export async function selectOrganizationByName(page: Page, name: string) {
  const selected = page.getByRole('button', { name: `Organization: ${name}` })
  if (await selected.isVisible()) return

  const trigger = page.getByRole('button', { name: /^Organization: / })
  await expect(trigger).toBeVisible()
  await trigger.click()
  await page.getByRole('menuitem', { name, exact: true }).click()
  await expect(selected).toBeVisible()
}

async function signIn(page: Page) {
  await signInAs(page, E2E_EMAIL, E2E_PASSWORD)
}

export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ page }, use) => {
    // Every authenticated fixture starts from a provably empty browser session.
    // This also protects fully-parallel suites that are constrained to one
    // worker from inheriting a session after a failed test teardown.
    await resetClientState(page)
    await signIn(page)
    await expect(page.locator('#vip-main')).toBeVisible()
    await selectOrganizationByName(page, E2E_ORGANIZATION_NAME)
    await use(page)
  },
})

export { expect, resetClientState, signIn }
