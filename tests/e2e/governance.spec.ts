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
  // Seed a pipeline in the shared governance workspace that the restricted persona
  // is never granted. This makes the collection filter and the direct-access guard
  // run against a REAL resource that exists in the persona's own workspace, so the
  // test proves resource-level authorization (not mere workspace scoping) and stays
  // deterministic in CI and locally regardless of any other seeded pipelines.
  await signInPersona(page, 'admin')
  const seeded = await page.evaluate(async () => {
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
    return {
      status: response.status,
      id: body?.pipeline?.id as string | undefined,
      version: body?.pipeline?.row_version as number | undefined,
    }
  })
  expect(seeded.status).toBe(201)
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
  // Dashboards stays hidden: its nav item requires the broad `dashboard.read`
  // permission (which the restricted role lacks) and the persona holds no
  // dashboard ACL, so neither the permission nor the entitlement path exposes it.
  await expect(page.getByRole('link', { name: 'Dashboards', exact: true })).toHaveCount(0)
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
    const create = await fetch('http://localhost:8000/api/v1/pipelines', {
      method: 'POST',
      credentials: 'include',
      headers,
      body: JSON.stringify({ name: 'Restricted must not create this pipeline' }),
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
      create: await read(create),
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
  // Direct access to that real, ungranted pipeline is a non-disclosing 404 —
  // seeing the nav link never implies access to a specific resource.
  expect(restricted.direct.status).toBe(404)
  // Unauthorized creation is denied by the broad create gate (no `pipeline.create`).
  expect(restricted.create.status).toBe(403)
  // Unauthorized execution is resource-evaluator denied: no operator ACL →
  // non-disclosing 404 (same contract as direct GET). Broad pipeline.execute is
  // no longer the run gate.
  expect(restricted.run.status).toBe(404)

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
