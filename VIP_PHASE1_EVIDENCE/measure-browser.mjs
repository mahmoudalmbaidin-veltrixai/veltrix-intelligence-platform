/* global process */
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'

const outputPath = path.resolve(process.argv[2])
const phase = process.argv[3] ?? 'after'
const screenshotPath = outputPath.replace(/\.json$/i, '.png')
const baseURL = 'http://localhost:3009'
const email = process.env.VIP_PHASE1_EMAIL
const password = process.env.VIP_PHASE1_PASSWORD
const organization = process.env.VIP_PHASE1_ORGANIZATION
const workspace = process.env.VIP_PHASE1_WORKSPACE
if (!email || !password || !organization || !workspace) throw new Error('Phase 1 fixture environment is incomplete.')

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
const consoleErrors = []
const pageErrors = []
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text().slice(0, 500))
})
page.on('pageerror', (error) => pageErrors.push(error.message.slice(0, 500)))

async function signIn() {
  await page.goto(`${baseURL}/login`)
  await page.getByLabel('Username or email').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await Promise.all([
    page.waitForResponse(
      (response) => response.url().endsWith('/auth/login') && response.request().method() === 'POST',
    ),
    page.getByRole('button', { name: 'Sign in', exact: true }).click(),
  ])
  await page.waitForURL(/\/home$/, { timeout: 20000 })
  const organizationButton = page.getByRole('button', { name: /^Organization: / })
  if (
    (await organizationButton.getAttribute('aria-label')) !== `Organization: ${organization}` &&
    !(await organizationButton.textContent())?.includes(organization)
  ) {
    await organizationButton.click()
    await page.getByRole('menuitem', { name: organization, exact: true }).click()
  }
  const workspaceButton = page.getByRole('button', { name: workspace, exact: true })
  if (await workspaceButton.count()) {
    const current = (await workspaceButton.first().textContent())?.trim()
    if (current !== workspace) {
      await workspaceButton.first().click()
      await page.getByRole('menuitem', { name: workspace, exact: true }).click()
    }
  }
}

function phaseRecorder() {
  const requests = []
  const failures = []
  const started = performance.now()
  const onRequest = (request) => {
    const url = request.url()
    if (url.includes('/api/v1/'))
      requests.push({ method: request.method(), url: new URL(url).pathname + new URL(url).search })
  }
  const onFailed = (request) => failures.push({ url: request.url(), error: request.failure()?.errorText ?? 'unknown' })
  page.on('request', onRequest)
  page.on('requestfailed', onFailed)
  return {
    finish(extra = {}) {
      page.off('request', onRequest)
      page.off('requestfailed', onFailed)
      return {
        duration_ms: Math.round(performance.now() - started),
        request_count: requests.length,
        dataset_list_requests: requests.filter((r) => /\/api\/v1\/datasets(?:\?|$)/.test(r.url)).length,
        quality_requests: requests.filter((r) => /\/api\/v1\/datasets\/[0-9a-f-]+\/quality(?:\?|$)/i.test(r.url))
          .length,
        pipeline_post_requests: requests.filter((r) => r.method === 'POST' && /\/api\/v1\/pipelines$/.test(r.url))
          .length,
        pipeline_put_requests: requests.filter(
          (r) => r.method === 'PUT' && /\/api\/v1\/pipelines\/[0-9a-f-]+$/i.test(r.url),
        ).length,
        failed_requests: failures,
        requests,
        ...extra,
      }
    },
  }
}

await signIn()

const datasetPhase = phaseRecorder()
await page.goto(`${baseURL}/datasets`)
let datasetSettled = true
try {
  await page
    .getByRole('heading', { name: /Datasets/i })
    .first()
    .waitFor({ state: 'visible', timeout: 20000 })
  await page
    .locator('.vip-skeleton, [aria-busy="true"]')
    .first()
    .waitFor({ state: 'hidden', timeout: 20000 })
    .catch(() => {})
  await page.waitForFunction(() => document.querySelectorAll('.vip-skeleton, [aria-busy="true"]').length === 0, null, {
    timeout: 20000,
  })
} catch {
  datasetSettled = false
}
const datasetListing = datasetPhase.finish({ settled: datasetSettled })

const sourcePhase = phaseRecorder()
await page.goto(`${baseURL}/pipelines/new`)
await page.getByRole('button', { name: /Add Dataset node/ }).press('Enter')
let sourceReady = true
try {
  await page.getByLabel('Dataset', { exact: true }).waitFor({ state: 'visible', timeout: 25000 })
  await page.waitForFunction(
    () => {
      const select = [...document.querySelectorAll('select')].find(
        (item) => item.labels?.[0]?.textContent?.trim() === 'Dataset',
      )
      return !!select && select.querySelectorAll('option').length > 1 && !select.disabled
    },
    null,
    { timeout: 25000 },
  )
} catch {
  sourceReady = false
}
const sourceSelector = sourcePhase.finish({ ready: sourceReady })

let firstSave = { completed: false, reason: 'source selector unavailable' }
let pipelineId = null
if (sourceReady) {
  const datasetSelect = page.getByLabel('Dataset', { exact: true })
  const options = await datasetSelect
    .locator('option')
    .evaluateAll((items) =>
      items.map((item) => ({ value: item.value, text: item.textContent ?? '' })).filter((item) => item.value),
    )
  const preferred = options.find((item) => item.text.includes('vip_b5_sales_demo')) ?? options[0]
  await datasetSelect.selectOption(preferred.value)
  await page
    .getByText(/Bound \d+ fields to this source/)
    .waitFor({ state: 'visible', timeout: 20000 })
    .catch(() => {})
  await page.getByLabel('Pipeline name').fill(`qa-phase1-${phase}-${Date.now()}`)
  const savePhase = phaseRecorder()
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  let stable = true
  try {
    await page.waitForURL(/\/pipelines\/[0-9a-f-]{36}$/i, { timeout: 25000 })
  } catch {
    stable = false
  }
  if (stable) pipelineId = page.url().split('/').at(-1)
  let persisted = false
  if (stable) {
    await page.reload()
    await page
      .getByRole('button', { name: /Dataset node:/ })
      .waitFor({ state: 'visible', timeout: 20000 })
      .catch(() => {})
    persisted = await page
      .getByRole('button', { name: /Dataset node:/ })
      .isVisible()
      .catch(() => false)
  }
  firstSave = savePhase.finish({
    completed: stable,
    pipeline_id_created: !!pipelineId,
    graph_persisted_after_reload: persisted,
  })
}

await page.screenshot({ path: screenshotPath, fullPage: true })

if (pipelineId) {
  await page.evaluate(async (id) => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}')
    const csrf = document.cookie
      .split('; ')
      .find((item) => item.startsWith('vip_csrf_token='))
      ?.split('=')[1]
    const headers = {
      'X-Organization-ID': preference.orgId ?? '',
      'X-Workspace-ID': preference.wsId ?? '',
      'X-CSRF-Token': csrf ? decodeURIComponent(csrf) : '',
    }
    const detail = await fetch(`http://localhost:8000/api/v1/pipelines/${id}`, {
      credentials: 'include',
      headers,
    }).then((response) => response.json())
    await fetch(`http://localhost:8000/api/v1/pipelines/${id}?expected_version=${detail.pipeline.row_version}`, {
      method: 'DELETE',
      credentials: 'include',
      headers,
    })
  }, pipelineId)
}

const result = {
  measured_at: new Date().toISOString(),
  dataset_listing: datasetListing,
  pipeline_source_selector: sourceSelector,
  first_save: firstSave,
  console_errors: consoleErrors,
  page_errors: pageErrors,
}
fs.mkdirSync(path.dirname(outputPath), { recursive: true })
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2))
await browser.close()
