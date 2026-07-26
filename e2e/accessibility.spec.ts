import AxeBuilder from '@axe-core/playwright'
import { test, expect, resetClientState } from './fixtures'

test.setTimeout(60_000)

const protectedRoutes = [
  '/home',
  '/dashboards',
  '/dashboards/new',
  '/pipelines',
  '/pipelines/new',
  '/settings/personal',
  '/admin/members',
  '/connections',
  '/datasets',
  '/developer',
  '/forbidden',
  '/not-found',
]

function blockingSummary(result: Awaited<ReturnType<AxeBuilder['analyze']>>) {
  return result.violations
    .filter((v) => ['critical', 'serious'].includes(v.impact ?? ''))
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) }))
}

test('@a11y collapsed navigation has no critical or serious automated violations', async ({
  authenticatedPage: page,
}) => {
  await page.getByRole('button', { name: 'Unpin and collapse navigation to icons' }).click()
  const result = await new AxeBuilder({ page }).analyze()
  expect(blockingSummary(result)).toEqual([])
})

test('@a11y mobile navigation drawer has no critical or serious automated violations', async ({
  authenticatedPage: page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(page.getByRole('dialog', { name: 'Navigation' })).toBeVisible()
  const result = await new AxeBuilder({ page }).analyze()
  expect(blockingSummary(result)).toEqual([])
})

test('@a11y dashboard share dialog has no critical or serious automated violations', async ({
  authenticatedPage: page,
}) => {
  await page.goto('/dashboards/new')
  await page.getByRole('textbox', { name: 'Dashboard name' }).fill(`Accessibility dashboard ${Date.now()}`)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboards\/[^/]+\/edit$/)
  await page.getByRole('button', { name: 'Share' }).click()
  await expect(page.getByRole('dialog', { name: 'Dashboard governance' })).toBeVisible()
  const result = await new AxeBuilder({ page }).analyze()
  expect(blockingSummary(result)).toEqual([])
})

test('@a11y login has no critical or serious automated violations', async ({ page }) => {
  await page.context().clearCookies()
  await resetClientState(page)
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: /Sign in/ })).toBeVisible()
  const result = await new AxeBuilder({ page }).analyze()
  expect(blockingSummary(result)).toEqual([])
})

for (const route of ['/dashboards/new', '/pipelines/new']) {
  test(`@a11y mobile ${route} has no critical or serious automated violations`, async ({ authenticatedPage: page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(route)
    const readySurface =
      route === '/dashboards/new'
        ? page.getByRole('textbox', { name: 'Dashboard name' })
        : page.getByRole('textbox', { name: 'Pipeline name' })
    await expect(readySurface).toBeVisible({ timeout: 20_000 })
    const result = await new AxeBuilder({ page }).analyze()
    expect(blockingSummary(result)).toEqual([])
  })
}

for (const route of protectedRoutes) {
  test(`@a11y ${route} has no critical or serious automated violations`, async ({ authenticatedPage: page }) => {
    await page.goto(route)
    const main = page.locator('#vip-main')
    await expect(main).toBeVisible()
    await expect(main).not.toBeEmpty()
    await page.locator('.vip-fade-enter-active, .vip-fade-leave-active').waitFor({ state: 'detached' })
    const result = await new AxeBuilder({ page }).analyze()
    expect(blockingSummary(result)).toEqual([])
  })
}
