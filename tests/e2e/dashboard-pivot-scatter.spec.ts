import type { Page } from '@playwright/test'
import { expect, resetClientState, signInAs, test } from './fixtures'

test.setTimeout(90_000)

async function archiveDashboard(page: Page, dashboardId: string, headers: Record<string, string>) {
  const detailResponse = await page.request.get(`http://localhost:8000/api/v1/dashboards/${dashboardId}`, { headers })
  expect(detailResponse.status()).toBe(200)
  const detail = (await detailResponse.json()) as { row_version: number }
  const response = await page.request.delete(
    `http://localhost:8000/api/v1/dashboards/${dashboardId}?expected_version=${detail.row_version}`,
    { headers },
  )
  expect(response.status()).toBe(204)
}

test('configured Scatter and Pivot retain their types through save, reload, and publish', async ({ page }) => {
  // This governed tenant owns an existing published semantic model with four
  // dimensions and seven metrics, so browser validation uses real metadata.
  const email = process.env.VIP_E2E_GOVERNANCE_DEMO_EMAIL
  const password = process.env.VIP_E2E_GOVERNANCE_DEMO_PASSWORD
  if (!email || !password) throw new Error('Governance Demo browser credentials are required')
  await resetClientState(page)
  await signInAs(page, email, password)
  await expect(page.locator('#vip-main')).toBeVisible()
  const loadedModels = page.waitForResponse(
    (response) => response.request().method() === 'GET' && response.url().endsWith('/api/v1/semantic-models'),
  )
  await page.goto('/dashboards/new')
  const tenantHeaders = (await loadedModels).request().headers()
  const csrf = await page.evaluate(
    () =>
      document.cookie
        .split('; ')
        .find((item) => item.startsWith('vip_csrf_token='))
        ?.split('=')[1] ?? '',
  )
  const headers = {
    'X-Organization-ID': tenantHeaders['x-organization-id'] ?? '',
    'X-Workspace-ID': tenantHeaders['x-workspace-id'] ?? '',
    'X-CSRF-Token': decodeURIComponent(csrf),
  }
  await page.getByRole('tab', { name: 'Data', exact: true }).click()
  await page.getByRole('combobox').first().selectOption({ label: 'LIVE-UAT-Sales-Model' })
  await page.getByRole('tab', { name: 'Visuals', exact: true }).click()
  await page.getByLabel('Dashboard name').fill(`qa-phase2-pivot-scatter-${Date.now()}`)

  let dashboardId: string | undefined
  try {
    await page.getByRole('button', { name: 'Scatter Plot', exact: true }).click()
    await page.getByRole('button', { name: 'Pivot Table', exact: true }).click()
    const scatter = page.getByRole('button', { name: /Scatter Plot widget/ })
    const pivot = page.getByRole('button', { name: /Pivot Table widget/ })
    await expect(scatter).toBeVisible()
    await expect(pivot).toBeVisible()
    await scatter.press('Enter')
    await expect(page.getByTestId('scatter-inspector-error')).toHaveCount(0)

    const persisted = page.waitForResponse(
      (response) => response.request().method() === 'PUT' && response.url().endsWith('/editor'),
    )
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    const persistedResponse = await persisted
    dashboardId = new URL(persistedResponse.url()).pathname.split('/').at(-2)
    expect(persistedResponse.status(), await persistedResponse.text()).toBe(200)
    await expect(page).toHaveURL(/\/dashboards\/[0-9a-f-]+\/edit$/i)

    await page.reload()
    const reloadedScatter = page.getByRole('button', { name: /Scatter Plot widget/ })
    await expect(reloadedScatter).toBeVisible()
    await expect(page.getByRole('button', { name: /Pivot Table widget/ })).toBeVisible()
    await reloadedScatter.press('Enter')
    await expect(page.getByTestId('scatter-inspector-error')).toHaveCount(0)

    const published = page.waitForResponse(
      (response) => response.request().method() === 'POST' && response.url().endsWith('/publish'),
    )
    await page.getByRole('button', { name: 'Publish', exact: true }).click()
    expect((await published).status()).toBe(200)
    await expect(page.getByText('published', { exact: true })).toBeVisible()
  } finally {
    if (dashboardId) await archiveDashboard(page, dashboardId, headers)
  }
})
