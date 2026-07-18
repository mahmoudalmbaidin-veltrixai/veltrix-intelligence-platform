/**
 * Generic service-factory helper. Domain services expose an interface and two
 * implementations (Mock / Api); `defineService` selects the right one from
 * env config. Views/stores/composables depend on the returned instance, never
 * on a concrete class.
 *
 *   export const dashboardService = defineService(mockDashboardService, () => apiDashboardService)
 */
import { config } from '@/shared/config/env'

export function defineService<T>(mock: T, liveFactory: () => T): T {
  return config.apiMode === 'live' ? liveFactory() : mock
}
