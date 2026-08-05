import { expect, resetClientState, signInAs, test } from './fixtures'
import { browserFixtures } from './personas'

async function signInAdmin(page: Parameters<typeof signInAs>[0]) {
  await page.context().clearCookies()
  await resetClientState(page)
  await signInAs(page, browserFixtures.governanceAdmin.email, browserFixtures.governanceAdmin.password)
}

test('admin creates a live connection without credential disclosure and receives sanitized test result', async ({
  page,
}) => {
  test.setTimeout(60_000)
  await signInAdmin(page)
  const uniqueSecret = `b4-browser-secret-${Date.now()}`
  const result = await page.evaluate(
    async ({ uniqueSecret }) => {
      const tenant = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
        orgId?: string
        wsId?: string
      }
      const csrf = document.cookie
        .split('; ')
        .find((value) => value.startsWith('vip_csrf_token='))
        ?.split('=')[1]
      const headers = {
        'Content-Type': 'application/json',
        'X-Organization-ID': tenant.orgId ?? '',
        'X-Workspace-ID': tenant.wsId ?? '',
        'X-CSRF-Token': csrf ?? '',
      }
      const existingResponse = await fetch('http://localhost:8000/api/v1/connections?page_size=100', {
        credentials: 'include',
        headers,
      })
      const existing = (await existingResponse.json()) as { items?: Array<{ id: string; name: string }> }
      for (const connection of existing.items ?? []) {
        if (!connection.name.startsWith('Browser B4 ')) continue
        await fetch(`http://localhost:8000/api/v1/connections/${connection.id}/archive`, {
          method: 'POST',
          credentials: 'include',
          headers,
        })
      }
      const createResponse = await fetch('http://localhost:8000/api/v1/connections', {
        method: 'POST',
        credentials: 'include',
        headers,
        body: JSON.stringify({
          name: `Browser B4 ${Date.now()}`,
          description: 'Browser security verification',
          connection_type: 'postgresql',
          configuration: { host: '127.0.0.1', port: 5432, database: 'vip', username: 'vip' },
          credentials: { password: uniqueSecret },
        }),
      })
      const created = await createResponse.json()
      const detailResponse = await fetch(`http://localhost:8000/api/v1/connections/${created.id}`, {
        credentials: 'include',
        headers,
      })
      const detail = await detailResponse.json()
      const listResponse = await fetch('http://localhost:8000/api/v1/connections', { credentials: 'include', headers })
      const list = await listResponse.json()
      const testResponse = await fetch(`http://localhost:8000/api/v1/connections/${created.id}/test`, {
        method: 'POST',
        credentials: 'include',
        headers,
      })
      const tested = await testResponse.json()
      return { createStatus: createResponse.status, created, detail, list, tested }
    },
    { uniqueSecret },
  )
  expect(result.createStatus).toBe(201)
  expect(JSON.stringify(result)).not.toContain(uniqueSecret)
  expect(result.created.credentials_configured).toBe(true)
  expect(result.created).not.toHaveProperty('credentials')
  expect(result.detail).not.toHaveProperty('ciphertext')
  expect(result.list.items[0]).not.toHaveProperty('configuration')
  expect(result.tested.status).toBe('failed')
  expect(result.tested.error.code).toBe('CONNECTION_DESTINATION_BLOCKED')

  await page.goto(`/connections/${result.created.id}`)
  await expect(page.getByRole('heading', { name: result.created.name })).toBeVisible()
  await expect(page.getByText(uniqueSecret)).toHaveCount(0)
  await expect(page.getByText('Stored credentials are never returned or prefilled.')).toBeVisible()
})

test('viewer and restricted users cannot bypass connection mutations', async ({ page }) => {
  await page.context().clearCookies()
  await resetClientState(page)
  await signInAs(page, browserFixtures.governanceViewer.email, browserFixtures.governanceViewer.password)
  const viewer = await page.evaluate(async () => {
    const tenant = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const csrf = document.cookie
      .split('; ')
      .find((value) => value.startsWith('vip_csrf_token='))
      ?.split('=')[1]
    const response = await fetch('http://localhost:8000/api/v1/connections', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-Organization-ID': tenant.orgId ?? '',
        'X-Workspace-ID': tenant.wsId ?? '',
        'X-CSRF-Token': csrf ?? '',
      },
      body: JSON.stringify({ name: 'Denied', connection_type: 'postgresql', configuration: {}, credentials: {} }),
    })
    return { status: response.status, body: await response.json() }
  })
  expect(viewer.status).toBe(403)
  expect(viewer.body.error.code).toBe('PERMISSION_DENIED')

  await page.context().clearCookies()
  await resetClientState(page)
  await signInAs(page, browserFixtures.moduleRestricted.email, browserFixtures.moduleRestricted.password)
  await page.goto('/connections')
  await expect(page).toHaveURL(/\/connections/)
  const restrictedCreate = await page.evaluate(async () => {
    const tenant = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const csrf = document.cookie
      .split('; ')
      .find((value) => value.startsWith('vip_csrf_token='))
      ?.split('=')[1]
    const response = await fetch('http://localhost:8000/api/v1/connections', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-Organization-ID': tenant.orgId ?? '',
        'X-Workspace-ID': tenant.wsId ?? '',
        'X-CSRF-Token': csrf ?? '',
      },
      body: JSON.stringify({ name: 'Denied', connection_type: 'postgresql', configuration: {}, credentials: {} }),
    })
    return { status: response.status, body: await response.json() }
  })
  expect(restrictedCreate.status).toBe(403)
  expect(restrictedCreate.body.error.code).toBe('PERMISSION_DENIED')
})
