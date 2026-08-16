import { expect, resetClientState, signInAs, test } from './fixtures'
import { browserFixtures, type BrowserPersona } from './personas'
import { parseSemanticModelList } from './helpers/semanticModels'

/**
 * Live Semantic Studio persona matrix (Phase B9.1C).
 *
 * Drives the four seeded governance personas against a real semantic model in
 * their shared workspace and asserts the backend-resolved effective access the
 * Studio renders from (view / query / edit / manage) plus fail-closed direct-API
 * denial for the restricted persona. The exhaustive capability ladder — ACL
 * elevation, group grants, expiry, cross-tenant denial and query-execution
 * authorization — is proven in apps/api tests/integration/
 * test_resource_authorization_domains.py; this spec verifies the same contract
 * end-to-end through the live API the UI consumes.
 */

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

// Read a semantic-model endpoint in the persona's active tenant context.
async function apiGet(page: Parameters<typeof signInAs>[0], path: string) {
  return page.evaluate(async (p) => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const response = await fetch(`http://localhost:8000/api/v1${p}`, {
      credentials: 'include',
      headers: {
        'X-Organization-ID': preference.orgId ?? '',
        'X-Workspace-ID': preference.wsId ?? '',
      },
    })
    return { status: response.status, body: await response.json().catch(() => null) }
  }, path)
}

// Attempt a mutation (archive) that requires manage authority.
async function apiArchive(page: Parameters<typeof signInAs>[0], modelId: string) {
  return page.evaluate(async (id) => {
    const preference = JSON.parse(localStorage.getItem('vip.tenancy.preference') ?? '{}') as {
      orgId?: string
      wsId?: string
    }
    const csrf =
      document.cookie
        .split('; ')
        .find((value) => value.startsWith('vip_csrf_token='))
        ?.split('=')[1] ?? ''
    const response = await fetch(`http://localhost:8000/api/v1/semantic-models/${id}/archive`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-Organization-ID': preference.orgId ?? '',
        'X-Workspace-ID': preference.wsId ?? '',
        'X-CSRF-Token': csrf,
      },
    })
    return { status: response.status }
  }, modelId)
}

test('semantic personas render from backend-resolved effective access', async ({ page }) => {
  // Manager/Owner: sees the Studio, lists models, and holds manage on a real model.
  await signInPersona(page, 'admin')
  await expect(page.getByRole('link', { name: 'Semantic Models', exact: true })).toBeVisible()
  const adminList = await apiGet(page, '/semantic-models')
  expect(adminList.status).toBe(200)
  const models = parseSemanticModelList(adminList.body)
  const modelId = models.find((model) => model.name === browserFixtures.certificationSemanticModel)?.id
  expect(modelId, `missing exact semantic fixture ${browserFixtures.certificationSemanticModel}`).toBeTruthy()

  const adminDetail = await apiGet(page, `/semantic-models/${modelId as string}`)
  expect(adminDetail.status).toBe(200)
  // The Manager/Owner holds the top capability level (publish/manage).
  expect(adminDetail.body.access.allowed_levels).toContain('manage')
  expect(adminDetail.body.access.can_manage_access).toBe(true)

  // Editor: can edit but NOT publish/manage — the capability ladder tops out
  // below `manage`, so the Studio renders an editor (not a manager) surface.
  await signInPersona(page, 'editor')
  const editorDetail = await apiGet(page, `/semantic-models/${modelId as string}`)
  if (editorDetail.status === 200) {
    expect(editorDetail.body.access.allowed_levels).toContain('edit')
    expect(editorDetail.body.access.allowed_levels).not.toContain('manage')
  } else {
    expect([403, 404]).toContain(editorDetail.status)
  }

  // Viewer: read-only — never `edit` or `manage`; a manage-level mutation is denied.
  await signInPersona(page, 'viewer')
  const viewerDetail = await apiGet(page, `/semantic-models/${modelId as string}`)
  if (viewerDetail.status === 200) {
    expect(viewerDetail.body.access.allowed_levels).not.toContain('edit')
    expect(viewerDetail.body.access.allowed_levels).not.toContain('manage')
  } else {
    expect([403, 404]).toContain(viewerDetail.status)
  }
  const viewerArchive = await apiArchive(page, modelId as string)
  expect([403, 404]).toContain(viewerArchive.status)

  // Denied: the restricted persona cannot see or mutate the model at all.
  await signInPersona(page, 'restricted')
  const deniedDetail = await apiGet(page, `/semantic-models/${modelId as string}`)
  expect([403, 404]).toContain(deniedDetail.status)
  const deniedArchive = await apiArchive(page, modelId as string)
  expect([403, 404]).toContain(deniedArchive.status)
})

test('audit access and placeholder gating are persona-scoped', async ({ page }) => {
  // Manager: Audit Center is reachable and returns real events; placeholder
  // modules are gated out of the navigation and the entitlement set.
  await signInPersona(page, 'admin')
  await expect(page.getByRole('link', { name: 'Audit Center', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Reports', exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Insights', exact: true })).toHaveCount(0)

  const audit = await apiGet(page, '/audit-events?limit=1')
  expect(audit.status).toBe(200)

  const context = await apiGet(page, '/authorization/context')
  expect(context.status).toBe(200)
  expect(context.body.entitlements).toContain('semantic_layer')
  expect(context.body.entitlements).toContain('advanced_audit')
  // Placeholder modules are not granted. Direct routes fail closed to 404;
  // they must not render the unfinished module surface or a /upgrade paywall.
  for (const gated of ['report_studio', 'insights', 'marketplace', 'billing']) {
    expect(context.body.entitlements).not.toContain(gated)
  }

  // Restricted: audit read is denied and the Audit Center nav is hidden.
  await signInPersona(page, 'restricted')
  await expect(page.getByRole('link', { name: 'Audit Center', exact: true })).toHaveCount(0)
  const deniedAudit = await apiGet(page, '/audit-events?limit=1')
  expect([403, 404]).toContain(deniedAudit.status)
})
