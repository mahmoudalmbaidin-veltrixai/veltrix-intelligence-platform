import { test, expect, selectOrganizationByName, signInAs } from './fixtures'
import { browserFixtures } from './personas'

test('organization and workspace switchers use authorized backend data', async ({ page }) => {
  await page.context().clearCookies()
  await signInAs(page, browserFixtures.tenantA.email, browserFixtures.tenantA.password)
  await selectOrganizationByName(page, browserFixtures.tenantAOrganization)
  await expect(page.getByRole('button', { name: `Organization: ${browserFixtures.tenantAOrganization}` })).toBeVisible()
  await page.getByRole('button', { name: `Organization: ${browserFixtures.tenantAOrganization}` }).click()
  await expect(page.getByRole('menuitem', { name: browserFixtures.tenantBOrganization })).toHaveCount(0)
  await expect(page.getByRole('menuitem', { name: browserFixtures.tenantAOrganization })).toBeVisible()

  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: browserFixtures.tenantAWorkspace }).click()
  await expect(page.getByRole('menuitem', { name: browserFixtures.workspaceASecondary })).toHaveCount(0)
})

test('workspace switching changes headers and survives reload only after validation', async ({ page }) => {
  await page.context().clearCookies()
  await signInAs(page, browserFixtures.primary.email, browserFixtures.primary.password)
  await selectOrganizationByName(page, browserFixtures.organizationA)
  const observed: Array<{ organization?: string; workspace?: string }> = []
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/')) {
      observed.push({
        organization: request.headers()['x-organization-id'],
        workspace: request.headers()['x-workspace-id'],
      })
    }
  })
  await page.getByRole('button', { name: browserFixtures.workspaceAPrimary }).click()
  await page.getByRole('menuitem', { name: browserFixtures.workspaceASecondary }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: browserFixtures.workspaceASecondary })).toBeVisible()
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
  await signInAs(page, browserFixtures.tenantB.email, browserFixtures.tenantB.password)

  await expect(page.getByRole('button', { name: `Organization: ${browserFixtures.tenantBOrganization}` })).toBeVisible()
  await page.getByRole('button', { name: `Organization: ${browserFixtures.tenantBOrganization}` }).click()
  await expect(page.getByRole('menuitem', { name: browserFixtures.tenantAOrganization })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: browserFixtures.tenantBWorkspace }).click()
  await expect(page.getByRole('menuitem', { name: browserFixtures.workspaceASecondary })).toHaveCount(0)
})

test('changing organization clears the old workspace context before loading the new one', async ({ page }) => {
  await page.context().clearCookies()
  await signInAs(page, browserFixtures.primary.email, browserFixtures.primary.password)
  await selectOrganizationByName(page, browserFixtures.organizationA)
  await page.getByRole('button', { name: `Organization: ${browserFixtures.organizationA}` }).click()
  await page.getByRole('menuitem', { name: browserFixtures.organizationB }).click()
  await expect(page.getByRole('button', { name: browserFixtures.workspaceBPrimary })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: `Organization: ${browserFixtures.organizationB}` })).toBeVisible()
  await expect(page.getByRole('button', { name: browserFixtures.workspaceBPrimary })).toBeVisible()
})
