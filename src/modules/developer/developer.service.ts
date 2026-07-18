/**
 * Developer service (mock).
 *
 * INTEGRATION POINT
 *   Live backend:
 *     GET  /api/v1/developer/keys                 -> ApiKey[]
 *     POST /api/v1/developer/keys                 -> { key, secret }  (secret shown once)
 *     GET  /api/v1/developer/webhooks             -> Webhook[]
 *     GET  /api/v1/developer/webhooks/deliveries  -> WebhookDelivery[]
 *   Swap `developerService` for a live adapter; the contract is identical.
 *
 *   NOTE: The plaintext secret is returned exactly once at creation time and
 *   is NEVER persisted or retrievable afterwards (only the prefix is stored).
 */
import { latency, isoAgo, nowIso } from '@/shared/lib/mock'
import { apiClient } from '@/shared/lib/apiClient'
import { defineService } from '@/shared/services/serviceFactory'

export type ApiKeyStatus = 'active' | 'revoked'

export interface ApiKey {
  id: string
  name: string
  prefix: string
  scopes: string[]
  createdAt: string
  lastUsed: string
  status: ApiKeyStatus
}

export type WebhookStatus = 'active' | 'disabled'

export interface Webhook {
  id: string
  url: string
  events: string[]
  status: WebhookStatus
  lastDelivery: string
}

export type DeliveryStatus = 'success' | 'failed'

export interface WebhookDelivery {
  id: string
  event: string
  status: DeliveryStatus
  ts: string
  responseCode: number
}

export interface CreateKeyPayload {
  name: string
  scopes: string[]
}

/** Scopes selectable when creating an API key. */
export const API_SCOPES = [
  'read:connections',
  'read:pipelines',
  'write:pipelines',
  'run:pipelines',
  'read:datasets',
  'read:dashboards',
  'write:dashboards',
  'read:reports',
  'admin:webhooks',
]

/** Event types a webhook can subscribe to. */
export const WEBHOOK_EVENTS = [
  'pipeline.run.succeeded',
  'pipeline.run.failed',
  'dataset.certified',
  'dashboard.published',
  'report.approved',
  'automation.failed',
]

const KEYS: ApiKey[] = [
  {
    id: 'key_ci_deploy',
    name: 'ci-deploy',
    prefix: 'vip_live_a1b2',
    scopes: ['run:pipelines', 'read:pipelines'],
    createdAt: isoAgo(60 * 24 * 120),
    lastUsed: isoAgo(320),
    status: 'active',
  },
  {
    id: 'key_reporting',
    name: 'reporting-readonly',
    prefix: 'vip_live_c3d4',
    scopes: ['read:datasets', 'read:dashboards', 'read:reports'],
    createdAt: isoAgo(60 * 24 * 40),
    lastUsed: isoAgo(90),
    status: 'active',
  },
  {
    id: 'key_legacy',
    name: 'legacy-integration',
    prefix: 'vip_live_e5f6',
    scopes: ['read:connections'],
    createdAt: isoAgo(60 * 24 * 400),
    lastUsed: isoAgo(60 * 24 * 200),
    status: 'revoked',
  },
  {
    id: 'key_sandbox',
    name: 'sandbox-test',
    prefix: 'vip_test_9z8y',
    scopes: ['read:datasets', 'write:dashboards'],
    createdAt: isoAgo(60 * 24 * 8),
    lastUsed: isoAgo(1200),
    status: 'active',
  },
]

const WEBHOOKS: Webhook[] = [
  {
    id: 'wh_slack_ops',
    url: 'https://hooks.veltrix.com/ops/pipeline-alerts',
    events: ['pipeline.run.failed', 'automation.failed'],
    status: 'active',
    lastDelivery: isoAgo(45),
  },
  {
    id: 'wh_datacatalog',
    url: 'https://catalog.veltrix.internal/webhooks/certified',
    events: ['dataset.certified'],
    status: 'active',
    lastDelivery: isoAgo(140),
  },
  {
    id: 'wh_legacy_bi',
    url: 'https://legacy-bi.example.com/hook',
    events: ['dashboard.published', 'report.approved'],
    status: 'disabled',
    lastDelivery: isoAgo(60 * 24 * 30),
  },
]

const DELIVERIES: WebhookDelivery[] = [
  { id: 'dlv_01', event: 'pipeline.run.failed', status: 'success', ts: isoAgo(45), responseCode: 200 },
  { id: 'dlv_02', event: 'dataset.certified', status: 'success', ts: isoAgo(140), responseCode: 200 },
  { id: 'dlv_03', event: 'pipeline.run.failed', status: 'failed', ts: isoAgo(220), responseCode: 503 },
  { id: 'dlv_04', event: 'automation.failed', status: 'success', ts: isoAgo(300), responseCode: 202 },
  { id: 'dlv_05', event: 'dashboard.published', status: 'failed', ts: isoAgo(500), responseCode: 404 },
  { id: 'dlv_06', event: 'report.approved', status: 'success', ts: isoAgo(900), responseCode: 200 },
  { id: 'dlv_07', event: 'dataset.certified', status: 'success', ts: isoAgo(1400), responseCode: 200 },
]

let created: ApiKey[] = []

export interface DeveloperService {
  listKeys(): Promise<ApiKey[]>
  listWebhooks(): Promise<Webhook[]>
  listDeliveries(): Promise<WebhookDelivery[]>
  createKey(payload: CreateKeyPayload): Promise<{ key: ApiKey; secret: string }>
}

const mockDeveloperService: DeveloperService = {
  async listKeys(): Promise<ApiKey[]> {
    await latency()
    return [...created, ...KEYS].map((k) => ({ ...k }))
  },

  async listWebhooks(): Promise<Webhook[]> {
    await latency()
    return WEBHOOKS.map((w) => ({ ...w }))
  },

  async listDeliveries(): Promise<WebhookDelivery[]> {
    await latency()
    return DELIVERIES.map((d) => ({ ...d }))
  },

  async createKey(payload: CreateKeyPayload): Promise<{ key: ApiKey; secret: string }> {
    await latency(500, 900)
    const rand = Math.random().toString(36).slice(2, 10)
    const secretBody = Array.from({ length: 3 }, () => Math.random().toString(36).slice(2, 12)).join('')
    const key: ApiKey = {
      id: `key_new_${rand}`,
      name: payload.name,
      prefix: `vip_live_${rand.slice(0, 4)}`,
      scopes: payload.scopes,
      createdAt: nowIso(),
      lastUsed: nowIso(),
      status: 'active',
    }
    created = [key, ...created]
    return { key, secret: `${key.prefix}_${secretBody}` }
  },
}

const apiDeveloperService: DeveloperService = {
  listKeys: () => apiClient.get<ApiKey[]>('/developer/keys'),
  listWebhooks: () => apiClient.get<Webhook[]>('/developer/webhooks'),
  listDeliveries: () => apiClient.get<WebhookDelivery[]>('/developer/webhooks/deliveries'),
  createKey: (payload) => apiClient.post<{ key: ApiKey; secret: string }>('/developer/keys', payload),
}

export const developerService: DeveloperService = defineService(mockDeveloperService, () => apiDeveloperService)
