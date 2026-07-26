import { expect, resetClientState, signInAs, test } from './fixtures'

const passwords = {
  admin: process.env.VIP_GOVERNANCE_ADMIN_PASSWORD ?? process.env.VIP_E2E_PASSWORD ?? '',
  editor: process.env.VIP_GOVERNANCE_EDITOR_PASSWORD ?? process.env.VIP_E2E_PASSWORD ?? '',
  viewer: process.env.VIP_GOVERNANCE_VIEWER_PASSWORD ?? process.env.VIP_E2E_PASSWORD ?? '',
  restricted: process.env.VIP_GOVERNANCE_RESTRICTED_PASSWORD ?? process.env.VIP_E2E_PASSWORD ?? '',
}

async function signInPersona(page: Parameters<typeof signInAs>[0], persona: keyof typeof passwords): Promise<void> {
  await page.context().clearCookies()
  await resetClientState(page)
  await signInAs(page, `governance-${persona}@vip.demo`, passwords[persona])
}

test('admin and editor receive backend-resolved navigation', async ({ page }) => {
  await signInPersona(page, 'admin')
  await expect(page.getByRole('link', { name: 'Organization Admin', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Pipelines', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'AI Agents', exact: true })).toHaveCount(0)

  await signInPersona(page, 'editor')
  await expect(page.getByRole('link', { name: 'Dashboard Studio', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Organization Admin', exact: true })).toHaveCount(0)
})

test('viewer and restricted personas are fail-closed in UI and direct API calls', async ({ page }) => {
  await signInPersona(page, 'viewer')
  await expect(page.getByRole('link', { name: 'Dashboards', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Dashboard Studio', exact: true })).toHaveCount(0)
  const viewerDenial = await page.evaluate(async () => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const response = await fetch('http://localhost:8000/api/v1/roles', {
      credentials: 'include',
      headers: {
        'X-Organization-ID': preference.orgId ?? '',
        'X-Workspace-ID': preference.wsId ?? '',
      },
    })
    return { status: response.status, body: await response.json() }
  })
  expect(viewerDenial.status).toBe(403)
  expect(viewerDenial.body.error.code).toBe('PERMISSION_DENIED')

  await signInPersona(page, 'restricted')
  await expect(page.getByRole('link', { name: 'Dashboards', exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Pipelines', exact: true })).toHaveCount(0)
})

test('authorization bootstrap is tenant-scoped and exhausted quota blocks mutation', async ({ page }) => {
  await signInPersona(page, 'admin')
  const result = await page.evaluate(async () => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const headers = {
      'Content-Type': 'application/json',
      'X-Organization-ID': preference.orgId ?? '',
      'X-Workspace-ID': preference.wsId ?? '',
      'X-CSRF-Token':
        document.cookie
          .split('; ')
          .find((value) => value.startsWith('vip_csrf_token='))
          ?.split('=')[1] ?? '',
    }
    const contextResponse = await fetch('http://localhost:8000/api/v1/authorization/context', {
      credentials: 'include',
      headers,
    })
    const context = await contextResponse.json()
    const mutationResponse = await fetch(
      `http://localhost:8000/api/v1/organizations/${preference.orgId ?? ''}/workspaces`,
      {
        method: 'POST',
        credentials: 'include',
        headers,
        body: JSON.stringify({ name: 'Quota Must Block', slug: 'quota-must-block' }),
      },
    )
    return { context, mutationStatus: mutationResponse.status, mutation: await mutationResponse.json() }
  })
  expect(result.context.workspace_role).toBe('workspace_admin')
  expect(result.context.features.dashboard_studio).toBe(true)
  expect(result.context.features.ai_studio).toBe(false)
  expect(result.context.entitlements).toContain('dashboard_studio')
  expect(result.context.entitlements).not.toContain('developer_api')
  expect(result.context.quotas['workspaces.max'].remaining).toBe(0)
  expect(result.mutationStatus).toBe(403)
  expect(result.mutation.error.code).toBe('QUOTA_EXCEEDED')
})
