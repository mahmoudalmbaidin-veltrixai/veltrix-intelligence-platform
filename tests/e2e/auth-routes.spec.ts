import { E2E_EMAIL, E2E_PASSWORD, expect, resetClientState, test } from './fixtures'

test('unauthenticated direct protected route redirects and restores intent', async ({ page }) => {
  test.setTimeout(60_000)
  await page.context().clearCookies()
  await resetClientState(page)
  await page.goto('/dashboards')
  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole('heading', { name: /Sign in/ })).toBeVisible()
  await page.getByLabel('Username or email').fill(E2E_EMAIL)
  await page.locator('input[name="password"]').fill(E2E_PASSWORD)
  const submit = page.getByRole('button', { name: 'Sign in' })
  await expect(submit).toBeEnabled()
  await submit.click()
  await expect(page).toHaveURL(/\/dashboards$/)
})

test('login validation and expired-session state are safe', async ({ page }) => {
  await resetClientState(page)
  await page.goto('/login?expired=1')
  await expect(page.getByText('Session expired')).toBeVisible()
  await page.getByLabel('Username or email').fill('')
  await page.locator('input[name="password"]').fill('')
  await page.getByRole('button', { name: 'Sign in' }).click()
  expect(
    await page.getByLabel('Username or email').evaluate((el: HTMLInputElement) => el.validity.valueMissing),
  ).toBe(true)
  expect(
    await page.locator('input[name="password"]').evaluate((el: HTMLInputElement) => el.validity.valueMissing),
  ).toBe(true)
})

test('invalid credentials stay generic and real cookie session survives bootstrap refresh', async ({ page }) => {
  await resetClientState(page)
  await page.goto('/login')
  await page.getByLabel('Username or email').fill(`invalid-${Date.now()}@vip.invalid`)
  await page.locator('input[name="password"]').fill('definitely-not-the-password')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Sign-in failed' })).toContainText('Invalid email or password')

  await page.getByLabel('Username or email').fill(E2E_EMAIL)
  await page.locator('input[name="password"]').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/home$/)

  const cookies = await page.context().cookies()
  const access = cookies.find((cookie) => cookie.name === 'vip_access_session')
  const refresh = cookies.find((cookie) => cookie.name === 'vip_refresh_session')
  const csrf = cookies.find((cookie) => cookie.name === 'vip_csrf_token')
  expect(access?.httpOnly).toBe(true)
  expect(refresh?.httpOnly).toBe(true)
  expect(csrf?.httpOnly).toBe(false)

  const browserStorage = await page.evaluate(() => ({
    local: { ...localStorage },
    session: { ...sessionStorage },
  }))
  expect(Object.keys(browserStorage.local)).not.toContain('vip.auth.session')
  expect(Object.keys(browserStorage.session)).not.toContain('vip.auth.session')
  expect(JSON.stringify(browserStorage)).not.toContain(access?.value ?? 'missing-access-token')
  expect(JSON.stringify(browserStorage)).not.toContain(refresh?.value ?? 'missing-refresh-token')

  await page.context().clearCookies({ name: 'vip_access_session' })
  await page.reload()
  await expect(page).toHaveURL(/\/home$/)
  await expect(page.locator('#vip-main')).toBeVisible()
})

test('logout is durable and protected routes cannot be reopened', async ({ authenticatedPage: page }) => {
  test.setTimeout(60_000)
  await page.getByRole('button', { name: 'User menu' }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto('/pipelines')
  await expect(page).toHaveURL(/\/login/)
  await page.reload()
  await expect(page.getByRole('heading', { name: /Sign in/ })).toBeVisible()
})

test('unknown route resolves to 404', async ({ authenticatedPage: page }) => {
  test.setTimeout(60_000)
  await page.goto('/definitely-not-a-route')
  await expect(page.getByRole('heading', { name: /page not found/i })).toBeVisible({ timeout: 20_000 })
})
