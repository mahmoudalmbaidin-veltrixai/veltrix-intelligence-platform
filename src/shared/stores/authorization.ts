import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  governanceService,
  type AuthorizationContextDto,
  type QuotaDto,
} from '@/shared/services/governance/apiGovernanceService'
import { ApiError } from '@/shared/types/api'

export type AuthorizationStatus = 'idle' | 'loading' | 'ready' | 'error'

export const useAuthorizationStore = defineStore('authorization', () => {
  const context = ref<AuthorizationContextDto | null>(null)
  const status = ref<AuthorizationStatus>('idle')
  const error = ref<ApiError | null>(null)
  let bootstrapPromise: Promise<void> | null = null

  const initialized = computed(() => status.value === 'ready' || status.value === 'error')
  const role = computed(() => context.value?.workspace_role ?? context.value?.organization_role ?? '')
  const permissions = computed(() => context.value?.permissions ?? [])
  const features = computed(() => context.value?.features ?? {})
  const entitlements = computed(() => context.value?.entitlements ?? [])
  const quotas = computed(() => context.value?.quotas ?? {})

  async function bootstrap(force = false): Promise<void> {
    if (bootstrapPromise) return bootstrapPromise
    if (initialized.value && !force) return
    status.value = 'loading'
    error.value = null
    bootstrapPromise = governanceService
      .authorizationContext()
      .then((value) => {
        context.value = value
        status.value = 'ready'
      })
      .catch((cause: unknown) => {
        context.value = null
        error.value = ApiError.from(cause)
        status.value = 'error'
        throw error.value
      })
      .finally(() => {
        bootstrapPromise = null
      })
    return bootstrapPromise
  }

  function clear(): void {
    context.value = null
    status.value = 'idle'
    error.value = null
    bootstrapPromise = null
  }

  function can(permission?: string): boolean {
    return permission === undefined || permissions.value.includes(permission)
  }

  function flagEnabled(key: string): boolean {
    return features.value[key] === true
  }

  function entitled(key: string): boolean {
    return entitlements.value.includes(key)
  }

  function quota(key: string): QuotaDto | undefined {
    return quotas.value[key]
  }

  function quotaAvailable(key: string, amount = 1): boolean {
    const value = quota(key)
    return value !== undefined && (!value.hard || value.remaining >= amount)
  }

  return {
    context,
    status,
    error,
    initialized,
    role,
    permissions,
    features,
    entitlements,
    quotas,
    bootstrap,
    clear,
    can,
    flagEnabled,
    entitled,
    quota,
    quotaAvailable,
  }
})
