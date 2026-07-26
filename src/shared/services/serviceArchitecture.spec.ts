import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const services = [
  'home/home.service.ts',
  'semantic/semantic.service.ts',
  'insights/insights.service.ts',
  'developer/developer.service.ts',
  'operations/operations.service.ts',
  'ai/ai.service.ts',
  'automation/automation.service.ts',
  'marketplace/marketplace.service.ts',
  'reports/reports.service.ts',
  'billing/billing.service.ts',
  'datasets/datasets.service.ts',
  'dashboards/dashboards.service.ts',
]

describe('all module service adapter boundaries', () => {
  it.each(services)('%s has typed mock/live selection through the centralized client', (relative) => {
    const source = readFileSync(join(root, 'src', 'modules', relative), 'utf8')
    expect(source).toMatch(/export interface \w+Service/)
    expect(source).toMatch(/mock\w+Service/)
    expect(source).toMatch(/api\w+Service/)
    expect(source).toContain('apiClient')
    expect(source).toContain('defineService')
  })

  it('production views do not import concrete mock service implementations', () => {
    const moduleSources = services
      .map((relative) => readFileSync(join(root, 'src', 'modules', relative), 'utf8'))
      .join('\n')
    expect(moduleSources).not.toMatch(/export\s+const\s+mock\w+Service/)
  })

  it('B4 connections use only the live API and contain no production-path mock', () => {
    const source = readFileSync(join(root, 'src', 'modules', 'connections/connections.service.ts'), 'utf8')
    expect(source).toContain('apiClient')
    expect(source).toContain("'/api/v1/connections/types'")
    expect(source).not.toMatch(/mockConnection|defineService|\bSEED\b/)
  })

  it('B6.5 dashboard exports and deliveries use only live APIs', () => {
    const source = readFileSync(join(root, 'src', 'modules', 'dashboards/delivery.service.ts'), 'utf8')
    expect(source).toContain('apiClient')
    expect(source).toContain('createExport')
    expect(source).toContain('download-token')
    expect(source).not.toMatch(/mockDeliveryService|defineService|\bSEED\b/)
  })

  it('B7 pipelines use only live APIs and durable run endpoints', () => {
    const source = readFileSync(join(root, 'src', 'modules', 'pipelines/pipelines.service.ts'), 'utf8')
    expect(source).toContain('apiClient')
    expect(source).toContain('startRun')
    expect(source).toContain('/runs')
    expect(source).not.toMatch(/mockPipelineService|defineService|LocalStore|RECENT_RUNS|createRun/)
  })

  it('B2/B3 administration uses only live tenant and governance APIs', () => {
    const source = readFileSync(join(root, 'src', 'modules', 'admin/admin.service.ts'), 'utf8')
    expect(source).toContain('tenancyService')
    expect(source).toContain('governanceService')
    expect(source).not.toMatch(/mockAdminService|defineService|\bMEMBERS\b|\bPOLICIES\b/)
  })
})
