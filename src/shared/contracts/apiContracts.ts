import { z } from 'zod'
import { ApiError, type Page } from '@/shared/types/api'

const id = z.string().min(1)
const isoDate = z.string().datetime({ offset: true })

export const userSchema = z.object({
  id,
  name: z.string().min(1),
  username: z.string().optional(),
  // Email is optional — users can exist without one (username login).
  email: z.string().email().nullable().optional(),
  avatarColor: z.string().optional(),
  jobTitle: z.string().optional(),
  timezone: z.string().min(1),
  locale: z.string().min(2),
})

export const organizationSchema = z.object({
  id,
  name: z.string().min(1),
  slug: z.string().min(1),
  status: z.enum(['trial', 'active', 'suspended', 'disabled', 'pending-deletion']),
  plan: z.enum(['trial', 'team', 'business', 'enterprise']),
})

export const workspaceSchema = z.object({
  id,
  orgId: id,
  name: z.string().min(1),
  slug: z.string().min(1),
  archived: z.boolean(),
})

export const authContextSchema = z.object({
  user: userSchema,
  organization: organizationSchema,
  workspace: workspaceSchema,
  role: z.string().min(1),
  permissions: z.array(z.string()),
  entitlements: z.array(z.object({ key: z.string(), enabled: z.boolean(), limit: z.number().optional() })),
  featureFlags: z.record(z.string(), z.boolean()),
})

export const sessionSchema = z.object({
  token: z.string().optional(),
  expiresAt: z.string(),
  context: authContextSchema,
})

export const authenticationResponseSchema = z.object({
  user: z.object({
    id,
    username: z.string().optional(),
    email: z.string().email().nullable().optional(),
    display_name: z.string().min(1),
    status: z.enum(['pending', 'active', 'locked', 'disabled', 'suspended', 'deleted']),
    is_platform_admin: z.boolean().optional().default(false),
    must_change_password: z.boolean().optional().default(false),
    account_type: z.string().optional().default('standard'),
    job_title: z.string().nullable().optional(),
    department: z.string().nullable().optional(),
    phone: z.string().nullable().optional(),
    locale: z.string().nullable().optional(),
    timezone: z.string().nullable().optional(),
    avatar_url: z.string().nullable().optional(),
    preferences: z.record(z.string(), z.unknown()).optional().default({}),
    created_at: isoDate.nullable().optional(),
    last_login_at: isoDate.nullable().optional(),
    password_changed_at: isoDate.nullable().optional(),
  }),
  session: z.object({
    expires_at: isoDate,
    idle_expires_at: isoDate.nullable().optional(),
    idle_timeout_minutes: z.number().nullable().optional(),
    warning_minutes: z.number().nullable().optional(),
  }),
})

export const fieldErrorSchema = z.object({ field: z.string(), code: z.string().optional(), message: z.string() })
export const errorEnvelopeSchema = z.object({
  message: z.string().optional(),
  errors: z.array(fieldErrorSchema).optional(),
  traceId: z.string().optional(),
})

export const standardErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.array(z.object({ field: z.string().nullable().optional(), message: z.string() })).optional(),
    correlation_id: z.string().optional(),
  }),
})

export const pageDtoSchema = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    items: z.array(item),
    page: z.number().int().positive(),
    pageSize: z.number().int().positive(),
    total: z.number().int().nonnegative().optional(),
    totalItems: z.number().int().nonnegative().optional(),
    totalPages: z.number().int().nonnegative().optional(),
    cursor: z.string().optional(),
    nextCursor: z.string().optional(),
    previousCursor: z.string().optional(),
  })

export function normalizePage<T>(value: z.infer<ReturnType<typeof pageDtoSchema>>): Page<T> {
  const total = value.total ?? value.totalItems ?? value.items.length
  return {
    items: value.items as T[],
    total,
    page: value.page,
    pageSize: value.pageSize,
    totalPages: value.totalPages ?? Math.ceil(total / value.pageSize),
    cursor: value.cursor,
    nextCursor: value.nextCursor,
    previousCursor: value.previousCursor,
  }
}

export const asyncJobSchema = z.object({
  id,
  status: z.enum(['queued', 'running', 'succeeded', 'failed', 'cancelled', 'partially_completed']),
  progress: z.number().min(0).max(100),
  currentStep: z.string().optional(),
  startedAt: isoDate.optional(),
  completedAt: isoDate.optional(),
  result: z.unknown().optional(),
  error: z
    .object({ message: z.string(), code: z.string().optional(), correlationId: z.string().optional() })
    .optional(),
  canRetry: z.boolean(),
  canCancel: z.boolean(),
})

export const dashboardSummarySchema = z.object({
  id,
  name: z.string().min(1),
  status: z.enum(['draft', 'published']),
  owner: z.string(),
  tags: z.array(z.string()),
  updatedAt: z.string(),
  favorite: z.boolean(),
  pageCount: z.number().int().nonnegative(),
  widgetCount: z.number().int().nonnegative(),
})

export const pipelineSummarySchema = z.object({
  id,
  name: z.string().min(1),
  description: z.string(),
  slug: z.string().min(1),
  status: z.enum(['draft', 'published']),
  tags: z.array(z.string()),
  row_version: z.number().int().positive(),
  published_version: z.number().int().positive().nullable(),
  updated_at: isoDate,
  last_run_at: isoDate.nullable(),
  last_run_status: z.string().nullable(),
  node_count: z.number().int().nonnegative(),
})

/** Runtime DTO boundary: malformed live responses fail closed before reaching stores or views. */
export function parseContract<T>(schema: z.ZodType<T>, value: unknown, contractName: string): T {
  const parsed = schema.safeParse(value)
  if (parsed.success) return parsed.data
  throw new ApiError('unknown', `Invalid ${contractName} response.`, {
    detail: parsed.error.issues.map((issue) => `${issue.path.join('.')}: ${issue.message}`).join('; '),
  })
}
