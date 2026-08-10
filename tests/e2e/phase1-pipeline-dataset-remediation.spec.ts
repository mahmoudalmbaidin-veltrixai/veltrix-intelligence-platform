import { expect, test } from './fixtures'
import { browserFixtures } from './personas'
import type { Page } from '@playwright/test'

test.setTimeout(90_000)

async function cleanupPipeline(page: Page, pipelineId: string) {
  const status = await page.evaluate(async (id: string) => {
    const tenancy = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const csrf = document.cookie
      .split('; ')
      .find((item) => item.startsWith('vip_csrf_token='))
      ?.split('=')[1]
    const headers = {
      'X-Organization-ID': tenancy.orgId ?? '',
      'X-Workspace-ID': tenancy.wsId ?? '',
      'X-CSRF-Token': csrf ? decodeURIComponent(csrf) : '',
    }
    const detail = await fetch(`http://localhost:8000/api/v1/pipelines/${id}`, {
      credentials: 'include',
      headers,
    }).then((response) => response.json() as Promise<{ pipeline: { row_version: number } }>)
    return fetch(`http://localhost:8000/api/v1/pipelines/${id}?expected_version=${detail.pipeline.row_version}`, {
      method: 'DELETE',
      credentials: 'include',
      headers,
    }).then((response) => response.status)
  }, pipelineId)
  expect(status).toBe(204)
}

test('Phase 1 bounded source hydration and recoverable atomic first save', async ({ authenticatedPage: page }) => {
  const datasetRequests: Array<{ method: string; path: string }> = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname.startsWith('/api/v1/datasets')) {
      datasetRequests.push({ method: request.method(), path: url.pathname })
    }
  })

  await page.goto('/datasets')
  await expect(page.getByRole('heading', { name: /Datasets/i }).first()).toBeVisible()
  await expect(page.getByText(/of 165|of \d+/).first()).toBeVisible({ timeout: 20_000 })
  expect(datasetRequests.filter((request) => request.path === '/api/v1/datasets')).toHaveLength(1)
  expect(datasetRequests.filter((request) => /\/quality$/.test(request.path))).toHaveLength(0)

  datasetRequests.length = 0
  await page.goto('/pipelines/new')
  await page.getByRole('button', { name: 'Add Dataset node' }).press('Enter')
  await expect(page.getByLabel('Dataset', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Dataset', { exact: true }).locator('option')).not.toHaveCount(1, { timeout: 20_000 })
  const datasetSelect = page.getByLabel('Dataset', { exact: true })
  const healthyDatasetId = await datasetSelect.locator('option').nth(1).getAttribute('value')
  expect(healthyDatasetId).toBeTruthy()

  const searched = page.waitForResponse(
    (response) => response.url().includes('/api/v1/datasets?') && response.url().includes('search='),
  )
  await page.getByLabel('Search datasets').fill(browserFixtures.certificationDataset)
  expect((await searched).status()).toBe(200)
  const option = datasetSelect.locator('option').filter({ hasText: browserFixtures.certificationDataset })
  await expect(option).toHaveCount(1)
  const resetSearch = page.waitForResponse(
    (response) => response.url().includes('/api/v1/datasets?') && !response.url().includes('search='),
  )
  await page.getByLabel('Search datasets').fill('')
  expect((await resetSearch).status()).toBe(200)
  await datasetSelect.selectOption(healthyDatasetId!)
  await expect(page.getByText(/Bound \d+ fields to this source/)).toBeVisible({ timeout: 20_000 })

  expect(datasetRequests.filter((request) => request.path === '/api/v1/datasets')).toHaveLength(3)
  expect(datasetRequests.filter((request) => /\/quality$/.test(request.path))).toHaveLength(0)

  await page.getByLabel('Pipeline name').fill(`qa-phase1-e2e-${Date.now()}`)
  let failFirstCreate = true
  let createRequests = 0
  await page.route('**/api/v1/pipelines', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    createRequests += 1
    if (failFirstCreate) {
      failFirstCreate = false
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'TEMPORARY_FAILURE', message: 'Temporary save failure' } }),
      })
    }
    return route.continue()
  })

  const save = page.getByRole('button', { name: 'Save', exact: true })
  await save.evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect(page.locator('.pstudio__save-error')).toContainText(/changes are retained/i)
  await expect(page.getByTestId('pipeline-save-state')).toHaveText('SAVE_FAILED')
  expect(createRequests).toBe(1)
  await expect(page.getByRole('button', { name: /Dataset node:/ })).toBeVisible()

  await save.evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect(page).toHaveURL(/\/pipelines\/[0-9a-f-]{36}$/i, { timeout: 20_000 })
  expect(createRequests).toBe(2)
  await expect(page.getByTestId('pipeline-save-state')).toHaveText('SAVED')
  const pipelineId = page.url().split('/').at(-1)!

  await page.reload()
  await expect(page.getByRole('button', { name: /Dataset node:/ })).toBeVisible()
  await page.getByRole('button', { name: /Dataset node:/ }).press('Enter')
  await expect(page.getByLabel('Dataset', { exact: true })).toHaveValue(healthyDatasetId!)
  await cleanupPipeline(page, pipelineId)
})
