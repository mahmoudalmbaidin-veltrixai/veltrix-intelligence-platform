import { test, expect, resetClientState } from './fixtures'

test('password visibility toggle preserves value, focus, and accessible state', async ({ page }) => {
  await resetClientState(page)
  await page.goto('/login')

  const password = page.locator('input[name="password"]')
  await expect(password).toHaveAccessibleName(/Password/)
  await password.fill('Cursor-safe secret')
  await password.evaluate((input: HTMLInputElement) => input.setSelectionRange(7, 7))

  const show = page.getByRole('button', { name: 'Show password' })
  await show.focus()
  await show.press('Enter')
  await expect(password).toHaveAttribute('type', 'text')
  await expect(password).toHaveValue('Cursor-safe secret')
  await expect(password).toBeFocused()
  await expect(page.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true')

  await page.getByRole('button', { name: 'Hide password' }).click()
  await expect(password).toHaveAttribute('type', 'password')
  await expect(password).toHaveValue('Cursor-safe secret')
})

test('@mobile login remains usable at 320px', async ({ page }) => {
  await resetClientState(page)
  await page.setViewportSize({ width: 320, height: 568 })
  await page.goto('/login')

  const card = page.locator('.login__card')
  await expect(card).toBeVisible()
  expect(await card.evaluate((element) => element.getBoundingClientRect().width)).toBeGreaterThanOrEqual(280)
  expect(await page.locator('html').evaluate((element) => element.scrollWidth)).toBe(320)
  await expect(page.getByLabel('Work email')).toBeVisible()
  await expect(page.locator('input[name="password"]')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
})

test('collapsed navigation stays discoverable, can be pinned, and persists', async ({ authenticatedPage: page }) => {
  const nav = page.getByRole('navigation', { name: 'Primary navigation' })
  await expect(nav).toHaveAttribute('aria-expanded', 'true')

  await page.getByRole('button', { name: 'Unpin and collapse navigation to icons' }).click()
  await expect(nav).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('button', { name: 'Pin navigation open' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Pipelines', exact: true })).toBeVisible()

  const pipelines = page.locator('a[href="/pipelines"]').first()
  await pipelines.hover()
  await expect(page.getByRole('tooltip').filter({ hasText: 'Pipelines' })).toBeVisible()

  await expect(nav).toHaveAttribute('aria-expanded', 'true')

  await page.keyboard.press('Escape')
  await expect(nav).toHaveAttribute('aria-expanded', 'false')
  await page.getByRole('button', { name: 'Pin navigation open' }).click()
  await expect(nav).toHaveAttribute('aria-expanded', 'true')
  await page.reload()
  await expect(nav).toHaveAttribute('aria-expanded', 'true')
})

test('sidebar shortcut toggles navigation but does not intercept text editing', async ({ authenticatedPage: page }) => {
  const nav = page.getByRole('navigation', { name: 'Primary navigation' })
  await page.keyboard.press('Control+b')
  await expect(nav).toHaveAttribute('aria-expanded', 'false')
  await page.keyboard.press('Control+b')
  await expect(nav).toHaveAttribute('aria-expanded', 'true')

  await page.goto('/dashboards/new')
  const title = page.getByLabel('Dashboard name')
  await title.focus()
  await page.keyboard.press('Control+b')
  await page.goto('/home')
  await expect(nav).toHaveAttribute('aria-expanded', 'true')
})

test('@mobile navigation drawer closes with Escape and returns focus', async ({ authenticatedPage: page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const clippedTopbarControls = await page.locator('header button').evaluateAll(
    (buttons) =>
      buttons.filter((button) => {
        const rect = button.getBoundingClientRect()
        const visible = getComputedStyle(button).display !== 'none' && rect.width > 0 && rect.height > 0
        return visible && (rect.left < 0 || rect.right > window.innerWidth)
      }).length,
  )
  expect(clippedTopbarControls).toBe(0)
  const trigger = page.getByRole('button', { name: 'Open navigation' })
  await trigger.click()
  await expect(page.getByRole('dialog', { name: 'Navigation' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Close' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'Navigation' })).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('@mobile compact shell keeps every visible top-bar control in the viewport', async ({
  authenticatedPage: page,
}) => {
  await page.setViewportSize({ width: 320, height: 568 })
  const clippedControls = await page.locator('header button').evaluateAll(
    (buttons) =>
      buttons.filter((button) => {
        const rect = button.getBoundingClientRect()
        const visible = getComputedStyle(button).display !== 'none' && rect.width > 0 && rect.height > 0
        return visible && (rect.left < 0 || rect.right > window.innerWidth)
      }).length,
  )
  expect(clippedControls).toBe(0)
  await expect(page.getByLabel('Application is running in hybrid local mode')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'User menu' })).toBeVisible()
})
