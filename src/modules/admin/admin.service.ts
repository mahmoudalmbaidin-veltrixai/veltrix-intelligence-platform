/**
 * Administration service (mock).
 * INTEGRATION POINT: /api/v1/admin/{organizations,members,workspaces,policies}
 * permission: admin:platform / admin:org / admin:workspace
 */
import { latency, isoAgo } from '@/shared/lib/mock'
import type { TenantStatus } from '@/shared/types/identity'

export interface OrgRow { id: string; name: string; status: TenantStatus; plan: string; members: number; createdAt: string }
export interface Member { id: string; name: string; email: string; role: string; status: 'active' | 'invited' | 'suspended'; lastActive: string }
export interface WorkspaceRow { id: string; name: string; members: number; archived: boolean; createdAt: string }
export interface Policy { key: string; label: string; description: string; value: boolean | string }

const ORGS: OrgRow[] = [
  { id: 'org_veltrix', name: 'Veltrix Global', status: 'active', plan: 'Enterprise', members: 248, createdAt: isoAgo(60 * 24 * 800) },
  { id: 'org_northwind', name: 'Northwind Trading', status: 'trial', plan: 'Trial', members: 12, createdAt: isoAgo(60 * 24 * 12) },
  { id: 'org_contoso', name: 'Contoso Retail', status: 'active', plan: 'Business', members: 74, createdAt: isoAgo(60 * 24 * 300) },
  { id: 'org_fabrikam', name: 'Fabrikam Health', status: 'suspended', plan: 'Business', members: 33, createdAt: isoAgo(60 * 24 * 500) },
  { id: 'org_initech', name: 'Initech Systems', status: 'pending-deletion', plan: 'Team', members: 5, createdAt: isoAgo(60 * 24 * 90) },
]

const MEMBERS: Member[] = [
  { id: 'm1', name: 'Mahmoud Almbaidin', email: 'mahmoud.almbaidin@shabakkatksa.com', role: 'Workspace Administrator', status: 'active', lastActive: isoAgo(4) },
  { id: 'm2', name: 'Aisha Rahman', email: 'aisha.rahman@veltrix.com', role: 'Analyst', status: 'active', lastActive: isoAgo(60) },
  { id: 'm3', name: 'David Chen', email: 'david.chen@veltrix.com', role: 'Data Engineer', status: 'active', lastActive: isoAgo(180) },
  { id: 'm4', name: 'Sofia Marín', email: 'sofia.marin@veltrix.com', role: 'Report Author', status: 'active', lastActive: isoAgo(600) },
  { id: 'm5', name: 'Tom Becker', email: 'tom.becker@veltrix.com', role: 'Business Viewer', status: 'invited', lastActive: isoAgo(60 * 24 * 3) },
  { id: 'm6', name: 'Priya Nair', email: 'priya.nair@veltrix.com', role: 'Developer', status: 'suspended', lastActive: isoAgo(60 * 24 * 30) },
]

const WORKSPACES: WorkspaceRow[] = [
  { id: 'ws_analytics', name: 'Analytics', members: 42, archived: false, createdAt: isoAgo(60 * 24 * 400) },
  { id: 'ws_revops', name: 'Revenue Ops', members: 18, archived: false, createdAt: isoAgo(60 * 24 * 200) },
  { id: 'ws_platform', name: 'Platform', members: 26, archived: false, createdAt: isoAgo(60 * 24 * 300) },
  { id: 'ws_legacy', name: 'Legacy Reporting', members: 3, archived: true, createdAt: isoAgo(60 * 24 * 900) },
]

const POLICIES: Policy[] = [
  { key: 'retention', label: 'Data retention', description: 'Days audit and run history are retained.', value: '365 days' },
  { key: 'mfa', label: 'Enforce MFA', description: 'Require multi-factor authentication for all members.', value: true },
  { key: 'session', label: 'Session duration', description: 'Idle timeout before re-authentication.', value: '8 hours' },
  { key: 'domains', label: 'Allowed email domains', description: 'Restrict membership to approved domains.', value: 'veltrix.com, shabakkatksa.com' },
  { key: 'wscreate', label: 'Workspace creation', description: 'Who can create new workspaces.', value: 'Admins only' },
  { key: 'external', label: 'External sharing', description: 'Allow sharing outside the organization.', value: false },
  { key: 'ai', label: 'AI usage', description: 'Allow AI features on workspace data.', value: true },
  { key: 'apikeys', label: 'API-key usage', description: 'Allow members to create API keys.', value: true },
]

export const adminService = {
  async listOrgs() { await latency(); return ORGS.map((o) => ({ ...o })) },
  async listMembers() { await latency(); return MEMBERS.map((m) => ({ ...m })) },
  async listWorkspaces() { await latency(); return WORKSPACES.map((w) => ({ ...w })) },
  async listPolicies() { await latency(); return POLICIES.map((p) => ({ ...p })) },
}

export const ASSIGNABLE_ROLES = [
  'Organization Owner', 'Organization Administrator', 'Workspace Administrator',
  'Data Engineer', 'Analyst', 'Report Author', 'Business Viewer', 'Developer',
]
