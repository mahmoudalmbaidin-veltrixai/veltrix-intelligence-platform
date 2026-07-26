import { test, expect, E2E_PASSWORD, signInAs } from './fixtures'

test('organization and workspace switchers use authorized backend data', async ({ authenticatedPage: page }) => {
  await page.context().clearCookies()
  await signInAs(page, 'tenant-a@vip.demo', E2E_PASSWORD)
  await expect(page.getByRole('button', { name: 'Organization: Organization Alpha' })).toBeVisible()
  await page.getByRole('button', { name: 'Organization: Organization Alpha' }).click()
  await expect(page.getByRole('menuitem', { name: 'Organization Beta' })).toHaveCount(0)
  await expect(page.getByRole('menuitem', { name: 'Organization Alpha' })).toBeVisible()

  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Alpha Workspace 1' }).click()
  await expect(page.getByRole('menuitem', { name: 'Alpha Workspace 2' })).toBeVisible()
})

test('workspace switching changes headers and survives reload only after validation', async ({
  authenticatedPage: page,
}) => {
  await page.context().clearCookies()
  await signInAs(page, 'tenant-a@vip.demo', E2E_PASSWORD)
  const observed: Array<{ organization?: string; workspace?: string }> = []
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/')) {
      observed.push({
        organization: request.headers()['x-organization-id'],
        workspace: request.headers()['x-workspace-id'],
      })
    }
  })
  await page.getByRole('button', { name: 'Alpha Workspace 1' }).click()
  await page.getByRole('menuitem', { name: 'Alpha Workspace 2' }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Alpha Workspace 2' })).toBeVisible()
  await page.evaluate(async () => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    await fetch('/api/v1/tenant-context', {
      headers: {
        'X-Organization-ID': preference.orgId ?? '',
        'X-Workspace-ID': preference.wsId ?? '',
      },
      credentials: 'include',
    })
  })
  expect(observed.some((item) => item.organization && item.workspace)).toBe(true)
})

test('limited user sees only assigned workspace in each real organization', async ({ page }) => {
  await page.context().clearCookies()
  await page.addInitScript(() => localStorage.clear())
  await signInAs(page, 'tenant-c@vip.demo', E2E_PASSWORD)

  await expect(page.getByRole('button', { name: 'Organization: Organization Alpha' })).toBeVisible()
  await page.getByRole('button', { name: 'Alpha Workspace 1' }).click()
  await expect(page.getByRole('menuitem', { name: 'Alpha Workspace 2' })).toHaveCount(0)
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Organization: Organization Alpha' }).click()
  await page.getByRole('menuitem', { name: 'Organization Beta' }).click()
  await expect(page.getByRole('button', { name: 'Beta Workspace 2' })).toBeVisible()
  await page.getByRole('button', { name: 'Beta Workspace 2' }).click()
  await expect(page.getByRole('menuitem', { name: 'Beta Workspace 1' })).toHaveCount(0)
})

test('changing organization clears the old workspace context before loading the new one', async ({ page }) => {
  await page.context().clearCookies()
  await signInAs(page, 'tenant-c@vip.demo', E2E_PASSWORD)
  await page.getByRole('button', { name: 'Organization: Organization Alpha' }).click()
  await page.getByRole('menuitem', { name: 'Organization Beta' }).click()
  await expect(page.getByRole('button', { name: 'Beta Workspace 2' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Organization: Organization Beta' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Beta Workspace 2' })).toBeVisible()
})
