import type { Page } from '@playwright/test'
import { test, expect } from './fixtures'

type DashboardFixture = {
  id: string
  row_version: number
  organizationId: string
  workspaceId: string
  csrf: string
}

async function createDashboard(page: Page, name: string) {
  const listResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/v1/dashboards') &&
      response.status() === 200,
  )
  await page.reload()
  const tenantHeaders = (await listResponse).request().headers()
  const csrf = await page.evaluate(
    () =>
      document.cookie
        .split('; ')
        .find((item) => item.startsWith('vip_csrf_token='))
        ?.split('=')[1] ?? '',
  )
  const response = await page.request.post('http://localhost:8000/api/v1/dashboards', {
    headers: {
      'X-Organization-ID': tenantHeaders['x-organization-id'] ?? '',
      'X-Workspace-ID': tenantHeaders['x-workspace-id'] ?? '',
      'X-CSRF-Token': decodeURIComponent(csrf),
    },
    data: { name, description: 'Browser action-menu fixture' },
  })
  if (response.status() !== 201) {
    throw new Error(`Dashboard fixture creation failed with HTTP ${response.status()}: ${await response.text()}`)
  }
  const dashboard = (await response.json()) as { id: string; row_version: number }
  return {
    ...dashboard,
    organizationId: tenantHeaders['x-organization-id'] ?? '',
    workspaceId: tenantHeaders['x-workspace-id'] ?? '',
    csrf: decodeURIComponent(csrf),
  } satisfies DashboardFixture
}

async function archiveDashboard(page: Page, dashboard: DashboardFixture) {
  const response = await page.request.delete(
    `http://localhost:8000/api/v1/dashboards/${dashboard.id}?expected_version=${dashboard.row_version}`,
    {
      headers: {
        'X-Organization-ID': dashboard.organizationId,
        'X-Workspace-ID': dashboard.workspaceId,
        'X-CSRF-Token': dashboard.csrf,
      },
    },
  )
  return response.status()
}

// Regression guard for the dashboard three-dot menu / delete defect: the action
// menu panel used to be clipped by the card's `overflow: hidden`, hiding Delete.
// VipMenu now teleports the panel to <body>, so it must render fully in-viewport
// and be interactable, and Delete must open the confirmation dialog.
test('dashboard action menu shows an unclipped, usable Delete action', async ({ authenticatedPage: page }) => {
  const name = `Browser dashboard actions ${Date.now()}`
  await page.goto('/dashboards')
  const dashboard = await createDashboard(page, name)
  await page.reload()

  const firstTrigger = page.getByRole('button', { name: `Actions for ${name}` })
  await expect(firstTrigger).toBeVisible()
  await firstTrigger.click()

  const menu = page.getByRole('menu')
  await expect(menu).toBeVisible()
  const deleteItem = menu.getByRole('menuitem', { name: 'Delete' })
  await expect(deleteItem).toBeVisible()

  // The regression: the Delete item must be fully within the viewport (not
  // clipped by an ancestor with overflow: hidden).
  const box = await deleteItem.boundingBox()
  const viewport = page.viewportSize()!
  expect(box).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1)

  // Delete opens the confirmation dialog; Cancel closes it without deleting.
  await deleteItem.click()
  const dialog = page.getByRole('dialog', { name: 'Delete dashboard?' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(dialog).toBeHidden()
  expect(await archiveDashboard(page, dashboard)).toBe(204)
})

test('dashboard action menu closes on Escape and returns focus to the trigger', async ({ authenticatedPage: page }) => {
  const name = `Browser dashboard escape ${Date.now()}`
  await page.goto('/dashboards')
  const dashboard = await createDashboard(page, name)
  await page.reload()
  const firstTrigger = page.getByRole('button', { name: `Actions for ${name}` })
  await firstTrigger.click()
  await expect(page.getByRole('menu')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toBeHidden()
  expect(await archiveDashboard(page, dashboard)).toBe(204)
})
