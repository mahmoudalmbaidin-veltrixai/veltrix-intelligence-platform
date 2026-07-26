import path from 'node:path'
import { test, expect } from './fixtures'

test.setTimeout(120_000)

test('Pipeline Studio uploads, previews, persists, and publishes a governed CSV source', async ({
  authenticatedPage: page,
}) => {
  const suffix = Date.now().toString()
  const datasetName = `B8.5 UI Source ${suffix}`
  // The certification connection points at the local demo warehouse. Its
  // externally managed objects use the established vip_b5_ namespace so
  // Alembic never mistakes tenant data for platform schema.
  const tableName = `vip_b5_b85_ui_source_${suffix}`
  const pipelineName = `B8.5 UI Pipeline ${suffix}`

  await page.goto('/pipelines/new')
  await page.getByRole('button', { name: 'Add Dataset node' }).press('Enter')
  await expect(page.getByLabel('Source type')).toBeVisible()
  await page.getByLabel('Source type').selectOption('file')
  await page.getByLabel('Destination connection').selectOption({ index: 1 })
  await page.getByLabel('Destination schema').fill('public')
  await page.getByLabel('Destination table').fill(tableName)
  await page.getByLabel('Dataset name').fill(datasetName)
  await page
    .getByLabel('CSV file')
    .setInputFiles(path.resolve('e2e', 'data', 'b8_5_certification.csv'))
  await page.getByRole('button', { name: 'Upload and register' }).click()

  await expect(page.getByText(/Bound \d+ fields to this source/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('transaction_id', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('B850001', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: /Output output port/ }).press('Enter')
  await page.getByRole('button', { name: 'Add Protected File node' }).press('Enter')
  await page.getByRole('button', { name: /Input input port/ }).press('Enter')
  const sourceBeforeSave = page.getByRole('button', { name: /Dataset node:/ })
  await sourceBeforeSave.focus()
  await sourceBeforeSave.press('Enter')
  await expect(page.getByLabel('Dataset', { exact: true })).toHaveValue(/.+/)
  await page.getByLabel('Pipeline name').fill(pipelineName)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page).toHaveURL(/\/pipelines\/[0-9a-f-]{36}$/)
  const pipelineId = page.url().split('/').at(-1)!

  await page.reload()
  const restoredSource = page.getByRole('button', { name: /Dataset node:/ })
  await restoredSource.focus()
  await restoredSource.press('Enter')
  await expect(page.getByLabel('Dataset', { exact: true })).toHaveValue(/.+/)
  await expect(page.getByText('B850001', { exact: true })).toBeVisible({ timeout: 20_000 })
  await page.getByRole('button', { name: 'Validate' }).click()
  await expect(page.getByText('Validation passed', { exact: true })).toBeVisible()
  const published = page.waitForResponse(
    (response) => response.url().endsWith('/publish') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Publish' }).click()
  expect((await published).status()).toBe(201)
  await page.reload()
  await expect(page.getByText('published', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Run', exact: true }).click()
  await expect(page.getByText('Run succeeded', { exact: true })).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('.pstudio__run-meta').getByText(/Rows: [1-9]\d*/)).toBeVisible()

  await page.goto('/datasets')
  await page.getByPlaceholder('Search datasets, owners or tags').fill(datasetName)
  await page.getByText(datasetName, { exact: true }).click()
  await expect(page).toHaveURL(/\/datasets\/[0-9a-f-]{36}$/)
  const datasetId = page.url().split('/').at(-1)!
  await page.getByRole('tab', { name: 'Data preview' }).click()
  await expect(page.getByText('B850001', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Profile' }).click()
  await expect(page.getByText('Live statistics over 15 sampled rows.')).toBeVisible()

  const cleanup = await page.evaluate(
    async ({ pipelineId, datasetId }) => {
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
      const pipeline = await fetch(`http://localhost:8000/api/v1/pipelines/${pipelineId}`, {
        credentials: 'include',
        headers,
      }).then((response) => response.json() as Promise<{ pipeline: { row_version: number } }>)
      const pipelineResponse = await fetch(
        `http://localhost:8000/api/v1/pipelines/${pipelineId}?expected_version=${pipeline.pipeline.row_version}`,
        { method: 'DELETE', credentials: 'include', headers },
      )
      const datasetResponse = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}`, {
        method: 'DELETE',
        credentials: 'include',
        headers,
      })
      return [pipelineResponse.status, datasetResponse.status]
    },
    { pipelineId, datasetId },
  )
  expect(cleanup).toEqual([204, 204])
})
