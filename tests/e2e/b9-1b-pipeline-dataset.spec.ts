/**
 * Phase B9.1B focused live Chromium checks (Pipeline + Dataset).
 * Requires running API + frontend in VITE_API_MODE=live and governance demo users.
 */
import { expect, resetClientState, signInAs, test } from './fixtures'

const password =
  process.env.VIP_GOVERNANCE_ADMIN_PASSWORD ??
  process.env.VIP_E2E_PASSWORD ??
  'Enterprise review 2026!'

async function signInAdmin(page: Parameters<typeof signInAs>[0]) {
  await page.context().clearCookies()
  await resetClientState(page)
  await signInAs(page, 'governance-admin@vip.demo', password)
}

test('B9.1B pipeline studio exposes run controls and artifact empty state for admin', async ({ page }) => {
  test.setTimeout(60_000)
  await signInAdmin(page)
  await page.goto('/pipelines/new')
  await page.getByLabel('Pipeline name').fill(`B9.1B Disposable ${Date.now()}`)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page).toHaveURL(/\/pipelines\/[0-9a-f-]{36}$/)

  await expect(page.getByRole('button', { name: 'Run' })).toBeVisible()
  await page.getByRole('tab', { name: /^Results/ }).click()
  await expect(
    page.getByText(/Run the pipeline to see node results and artifacts|No artifacts for this run|Artifacts/i),
  ).toBeVisible()
})

test('B9.1B dataset detail live tabs have no fabricated mock rows', async ({ page }) => {
  test.setTimeout(60_000)
  await signInAdmin(page)
  await page.goto('/datasets')
  await expect(page.getByRole('heading', { name: /Datasets/i }).first()).toBeVisible({ timeout: 20_000 })

  // Resolve a real dataset id from the live API (list rows are not anchors).
  const datasetId = await page.evaluate(async () => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const response = await fetch('http://localhost:8000/api/v1/datasets?page_size=5', {
      credentials: 'include',
      headers: {
        'X-Organization-ID': preference.orgId ?? '',
        'X-Workspace-ID': preference.wsId ?? '',
      },
    })
    const body = (await response.json()) as { items?: Array<{ id: string }> }
    return body.items?.[0]?.id ?? null
  })
  expect(datasetId).toBeTruthy()
  await page.goto(`/datasets/${datasetId}`)
  await expect(page).toHaveURL(new RegExp(`/datasets/${datasetId}`, 'i'), { timeout: 20_000 })

  await expect(page.getByRole('heading', { name: 'Certification' })).toBeVisible()

  await page.getByRole('tab', { name: 'Lineage' }).click()
  await expect(page.getByText('Revenue Nightly ETL')).toHaveCount(0)
  await expect(page.getByText('Upstream', { exact: true })).toBeVisible()
  await expect(page.getByText('No upstream resources')).toBeVisible()

  await page.getByRole('tab', { name: 'Versions' }).click()
  await expect(page.getByText('Version history unavailable')).toBeVisible()
  await expect(page.getByText('Incremental refresh')).toHaveCount(0)

  await page.getByRole('tab', { name: 'Activity' }).click()
  await expect(page.getByText('refreshed the dataset')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Recent activity' })).toBeVisible()

  await page.getByRole('tab', { name: 'Access' }).click()
  await expect(page.getByText('analytics-service')).toHaveCount(0)
  await expect(page.getByText('No direct access grants').or(page.getByText('Principal', { exact: true }))).toBeVisible()
})
