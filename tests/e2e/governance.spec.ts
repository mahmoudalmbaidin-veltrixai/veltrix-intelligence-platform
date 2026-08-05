import { expect, resetClientState, signInAs, test } from './fixtures'
import { browserFixtures, type BrowserPersona } from './personas'

const personas: Record<'admin' | 'editor' | 'viewer' | 'restricted', BrowserPersona> = {
  admin: browserFixtures.governanceAdmin,
  editor: browserFixtures.governanceEditor,
  viewer: browserFixtures.governanceViewer,
  restricted: browserFixtures.governanceRestricted,
}

async function signInPersona(page: Parameters<typeof signInAs>[0], persona: keyof typeof personas): Promise<void> {
  await page.context().clearCookies()
  await resetClientState(page)
  await signInAs(page, personas[persona].email, personas[persona].password)
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
  // Seed a pipeline in the shared governance workspace that the restricted persona
  // is never granted. This makes the collection filter and the direct-access guard
  // run against a REAL resource that exists in the persona's own workspace, so the
  // test proves resource-level authorization (not mere workspace scoping) and stays
  // deterministic in CI and locally regardless of any other seeded pipelines.
  await signInPersona(page, 'admin')
  const seeded = await page.evaluate(async (restrictedUserId) => {
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
    const response = await fetch('http://localhost:8000/api/v1/pipelines', {
      method: 'POST',
      credentials: 'include',
      headers,
      body: JSON.stringify({ name: 'Governance E2E — restricted must never see this' }),
    })
    const body = await response.json().catch(() => null)
    let denyStatus: number | null = null
    if (response.status === 201 && body?.pipeline?.id) {
      const denyResponse = await fetch(
        `http://localhost:8000/api/v1/resources/pipeline/${body.pipeline.id}/access`,
        {
          method: 'POST',
          credentials: 'include',
          headers,
          body: JSON.stringify({
            subject_type: 'user',
            subject_id: restrictedUserId,
            access_level: 'viewer',
            effect: 'deny',
            expires_at: null,
          }),
        },
      )
      denyStatus = denyResponse.status
    }
    return {
      status: response.status,
      denyStatus,
      id: body?.pipeline?.id as string | undefined,
      version: body?.pipeline?.row_version as number | undefined,
    }
  }, browserFixtures.governanceRestrictedId)
  expect(seeded.status).toBe(201)
  expect(seeded.denyStatus).toBe(200)
  expect(seeded.id).toBeTruthy()
  const unauthorizedPipelineId = seeded.id as string

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
  // The persona intentionally has an Editor workspace role so modules may remain
  // discoverable. Its explicit resource deny is the security boundary exercised
  // below; module visibility must never be mistaken for resource access.
  await expect(page.getByRole('link', { name: 'Dashboards', exact: true })).toBeVisible()
  // Pipelines IS visible: the Pipelines module is now gated by the
  // `pipeline_studio` entitlement (not the broad `pipeline.read`), so any member
  // who could hold a resource-level ACL can reach their filtered list. Frontend
  // visibility is deliberately NOT the security boundary — the backend
  // fail-closes below regardless of the nav link.
  await expect(page.getByRole('link', { name: 'Pipelines', exact: true })).toBeVisible()

  // Navigation visibility must never equal access. The restricted persona has the
  // entitlement but no pipeline role and no pipeline ACL grant, so the backend
  // must: SQL-visibility-filter the collection so the admin-seeded pipeline is
  // hidden, return a non-disclosing 404 for it on direct access, and deny every
  // mutation/execution.
  const restricted = await page.evaluate(async (unauthorizedId) => {
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
    const read = async (response: Response) => ({
      status: response.status,
      body: await response.json().catch(() => null),
    })
    const list = await fetch('http://localhost:8000/api/v1/pipelines', {
      credentials: 'include',
      headers,
    })
    const direct = await fetch(`http://localhost:8000/api/v1/pipelines/${unauthorizedId}`, {
      credentials: 'include',
      headers,
    })
    const run = await fetch(`http://localhost:8000/api/v1/pipelines/${unauthorizedId}/runs`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: JSON.stringify({}),
    })
    return {
      list: await read(list),
      direct: await read(direct),
      run: await read(run),
    }
  }, unauthorizedPipelineId)
  // Collection is SQL-visibility-filtered: the entitled-but-ungranted member can
  // list pipelines, but the admin-seeded pipeline it was not granted is absent
  // (no leaked name, id, or total).
  expect(restricted.list.status).toBe(200)
  const restrictedItems = restricted.list.body?.items as Array<{ id: string }> | undefined
  expect(Array.isArray(restrictedItems)).toBe(true)
  expect(restrictedItems?.some((pipeline) => pipeline.id === unauthorizedPipelineId)).toBe(false)
  // Direct access and execution are explicit-deny 403 responses. The separate
  // no-grant personas cover the non-disclosing 404 branch in integration tests.
  expect(restricted.direct.status).toBe(403)
  expect(restricted.direct.body.error.code).toBe('RESOURCE_ACCESS_DENIED')
  expect(restricted.run.status).toBe(403)
  expect(restricted.run.body.error.code).toBe('RESOURCE_ACCESS_DENIED')

  // Best-effort cleanup so repeated local runs don't accumulate fixtures (the CI
  // database is ephemeral). Not asserted — the checks above already used a fresh id.
  await signInPersona(page, 'admin')
  await page.evaluate(
    async ({ id, version }) => {
      const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
        orgId?: string
        wsId?: string
      }
      const headers = {
        'X-Organization-ID': preference.orgId ?? '',
        'X-Workspace-ID': preference.wsId ?? '',
        'X-CSRF-Token':
          document.cookie
            .split('; ')
            .find((value) => value.startsWith('vip_csrf_token='))
            ?.split('=')[1] ?? '',
      }
      await fetch(`http://localhost:8000/api/v1/pipelines/${id}?expected_version=${version ?? 1}`, {
        method: 'DELETE',
        credentials: 'include',
        headers,
      }).catch(() => undefined)
    },
    { id: unauthorizedPipelineId, version: seeded.version },
  )
})

test('authorization bootstrap is tenant-scoped and exposes the live quota contract', async ({ page }) => {
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
    return { context, activeOrganizationId: preference.orgId, activeWorkspaceId: preference.wsId }
  })
  expect(result.context.workspace_role).toBe('workspace_admin')
  expect(result.context.features.dashboard_studio).toBe(true)
  expect(result.context.features.ai_studio).toBe(false)
  expect(result.context.entitlements).toContain('dashboard_studio')
  expect(result.context.entitlements).not.toContain('developer_api')
  const workspaceQuota = result.context.quotas['workspaces.max']
  expect(workspaceQuota.hard).toBe(true)
  expect(workspaceQuota.remaining).toBeGreaterThanOrEqual(0)
  expect(workspaceQuota.remaining).toBeLessThanOrEqual(workspaceQuota.limit)
  expect(result.context.organization_id).toBe(result.activeOrganizationId)
  expect(result.context.workspace_id).toBe(result.activeWorkspaceId)
})
