/**
 * Phase B9.1B focused live Chromium checks (Pipeline + Dataset).
 * Requires running API + frontend in VITE_API_MODE=live and governance demo users.
 */
import { expect, resetClientState, signInAs, test } from './fixtures'
import { browserFixtures } from './personas'

async function signInAdmin(page: Parameters<typeof signInAs>[0]) {
  await page.context().clearCookies()
  await resetClientState(page)
  await signInAs(page, browserFixtures.governanceAdmin.email, browserFixtures.governanceAdmin.password)
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
  test.setTimeout(90_000)
  await signInAdmin(page)
  await page.goto('/datasets')
  await expect(page.getByRole('heading', { name: /Datasets/i }).first()).toBeVisible({ timeout: 20_000 })

  // Resolve a dataset that has real persisted version history (VIP-BUG-010).
  const datasetId = await page.evaluate(async (expectedName) => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const headers = {
      'X-Organization-ID': preference.orgId ?? '',
      'X-Workspace-ID': preference.wsId ?? '',
    }
    const list = await fetch('http://localhost:8000/api/v1/datasets?page=1&page_size=100', {
      credentials: 'include',
      headers,
    })
    const body = (await list.json()) as { items?: Array<{ id: string; display_name: string }> }
    const items = body.items ?? []
    const preferred =
      items.find((dataset) => dataset.display_name === expectedName) ??
      items.find((dataset) => dataset.display_name.toLowerCase().includes('certif')) ??
      items[0]
    if (!preferred) return null

    // Prefer a dataset that already has version snapshots.
    for (const candidate of [preferred, ...items.filter((item) => item.id !== preferred.id)].slice(0, 25)) {
      const versionsResponse = await fetch(
        `http://localhost:8000/api/v1/datasets/${candidate.id}/versions`,
        { credentials: 'include', headers },
      )
      if (!versionsResponse.ok) continue
      const versions = (await versionsResponse.json()) as Array<{
        id: string
        version_number?: number
        versionNumber?: number
        version_type?: string
        versionType?: string
      }>
      if (Array.isArray(versions) && versions.length > 0) return candidate.id
    }
    return preferred.id
  }, browserFixtures.certificationDataset)
  expect(datasetId).toBeTruthy()
  await page.goto(`/datasets/${datasetId}`)
  await expect(page).toHaveURL(new RegExp(`/datasets/${datasetId}`, 'i'), { timeout: 20_000 })

  await expect(page.getByRole('heading', { name: 'Certification', exact: true })).toBeVisible()

  await page.getByRole('tab', { name: 'Lineage' }).click()
  await expect(page.getByText('Revenue Nightly ETL')).toHaveCount(0)
  await expect(page.getByText('Upstream', { exact: true })).toBeVisible()
  await expect(page.getByText('No upstream resources')).toBeVisible()

  await page.getByRole('tab', { name: 'Versions' }).click()
  // Obsolete placeholder expectation removed — product returns persisted history.
  await expect(page.getByText('Version history unavailable')).toHaveCount(0)
  await expect(page.getByText('Version history is unavailable.')).toHaveCount(0)
  await expect(page.getByText('Incremental refresh')).toHaveCount(0)
  const versionEntry = page.locator('.dd__version').first()
  await expect(versionEntry).toBeVisible({ timeout: 15_000 })
  await expect(versionEntry.getByText(/^v\d+/)).toBeVisible()
  await expect(versionEntry.locator('.vip-badge').filter({ hasText: /created|certified|restored/i })).toBeVisible()
  await expect(versionEntry.locator('.dd__muted')).not.toBeEmpty()
  await expect(versionEntry.locator('.dd__version-note')).toBeVisible()

  await page.getByRole('tab', { name: 'Activity' }).click()
  await expect(page.getByText('refreshed the dataset')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Recent activity' })).toBeVisible()

  await page.getByRole('tab', { name: 'Access' }).click()
  await expect(page.getByText('analytics-service')).toHaveCount(0)
  await expect(page.getByText('No direct access grants').or(page.getByText('Principal', { exact: true }))).toBeVisible()
})
