import { afterEach, describe, expect, it, vi } from 'vitest'
import { tenancyService } from './apiTenancyService'

describe('tenancy API service', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses real organization and scoped workspace endpoints', async () => {
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(url)
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )
    await tenancyService.listOrganizations()
    await tenancyService.listWorkspaces('org/value')
    await tenancyService.listWorkspaces('org/value', true)
    expect(calls[0]).toContain('/api/v1/organizations')
    expect(calls[1]).toContain('/api/v1/organizations/org%2Fvalue/workspaces')
    expect(calls[2]).toContain('/api/v1/organizations/org%2Fvalue/workspaces?include_archived=true')
  })

  it('persists organization and workspace mutations through tenant-scoped endpoints', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = []
    const organization = {
      id: 'org-id',
      name: 'Alpha Updated',
      slug: 'alpha-updated',
      status: 'active',
      membership: { role: 'organization_owner', status: 'active' },
    }
    const workspace = {
      id: 'workspace-id',
      organization_id: 'org/value',
      name: 'Live Workspace',
      slug: 'live-workspace',
      status: 'active',
      is_default: false,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, init })
        return new Response(JSON.stringify(url.endsWith('/org%2Fvalue') ? organization : workspace), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )

    await tenancyService.updateOrganization('org/value', { name: 'Alpha Updated', slug: 'alpha-updated' })
    await tenancyService.createWorkspace('org/value', { name: 'Live Workspace', slug: 'live-workspace' })
    await tenancyService.updateWorkspace('org/value', 'workspace/value', { status: 'archived' })

    expect(calls.map((call) => [call.init?.method, call.url])).toEqual([
      ['PATCH', '/api/v1/organizations/org%2Fvalue'],
      ['POST', '/api/v1/organizations/org%2Fvalue/workspaces'],
      ['PATCH', '/api/v1/organizations/org%2Fvalue/workspaces/workspace%2Fvalue'],
    ])
    expect(calls[1]?.init?.body).toBe(JSON.stringify({ name: 'Live Workspace', slug: 'live-workspace' }))
    expect(calls[2]?.init?.body).toBe(JSON.stringify({ status: 'archived' }))
  })
})
