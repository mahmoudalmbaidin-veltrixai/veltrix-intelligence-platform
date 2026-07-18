import { defineService } from '@/shared/services/serviceFactory'
import { mockAuthService } from './mockAuthService'
import { apiAuthService } from './apiAuthService'

export type { AuthService, Session, LoginCredentials } from './types'
export { seedMockSession } from './mockAuthService'

/** Selected at load time from VITE_API_MODE. */
export const authService = defineService(mockAuthService, () => apiAuthService)
