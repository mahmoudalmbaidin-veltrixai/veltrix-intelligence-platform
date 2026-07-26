import { apiClient } from '@/shared/lib/apiClient'

export interface QuotaDto {
  key: string
  limit: number
  used: number
  remaining: number
  hard: boolean
}

export interface AuthorizationContextDto {
  user_id: string
  organization_id: string
  workspace_id: string | null
  organization_role: string
  workspace_role: string | null
  permissions: string[]
  features: Record<string, boolean>
  entitlements: string[]
  quotas: Record<string, QuotaDto>
}

export interface RoleDto {
  id: string
  key: string
  name: string
  scope: 'organization' | 'workspace' | 'platform'
  is_assignable: boolean
  priority: number
  permissions: string[]
}

export const governanceService = {
  authorizationContext(): Promise<AuthorizationContextDto> {
    return apiClient.get('/api/v1/authorization/context', { retry: 0 })
  },
  roles(): Promise<RoleDto[]> {
    return apiClient.get('/api/v1/roles', { retry: 0 })
  },
}
