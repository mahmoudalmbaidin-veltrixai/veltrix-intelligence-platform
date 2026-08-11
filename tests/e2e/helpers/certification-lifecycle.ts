/**
 * Browser certification fixture lifecycle helper (VIP-BUG-009).
 */
export type CertResourceKind =
  | 'organization'
  | 'workspace'
  | 'user'
  | 'connection'
  | 'file'
  | 'dataset'
  | 'pipeline'
  | 'dashboard'
  | 'schedule'
  | 'export'

export interface CertResource {
  kind: CertResourceKind
  id: string
  name: string
  retain?: boolean
}

const CLEANUP_ORDER: CertResourceKind[] = [
  'export',
  'schedule',
  'dashboard',
  'pipeline',
  'dataset',
  'file',
  'connection',
  'user',
  'workspace',
  'organization',
]

export function newCertRunId(now = new Date()): string {
  const stamp = now.toISOString().slice(0, 10).replace(/-/g, '')
  const suffix = crypto.randomUUID().replace(/-/g, '').slice(0, 8)
  return `qa-cert-${stamp}-${suffix}`
}

export class CertificationFixtureRegistry {
  readonly runId: string
  private readonly resources: CertResource[] = []

  constructor(runId = newCertRunId()) {
    if (!/^qa-cert-\d{8}-[a-f0-9]{8}$/.test(runId)) {
      throw new Error(`Unsafe certification run id: ${runId}`)
    }
    this.runId = runId
  }

  namespaced(label: string): string {
    const safe = label.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80)
    return `${this.runId}-${safe}`
  }

  register(kind: CertResourceKind, id: string, name: string, retain = false): void {
    this.resources.push({ kind, id, name, retain })
  }

  markRetained(id: string): void {
    const item = this.resources.find((resource) => resource.id === id)
    if (item) item.retain = true
  }

  snapshot(): CertResource[] {
    return [...this.resources]
  }

  async cleanup(
    handlers: Partial<Record<CertResourceKind, (resource: CertResource) => Promise<void>>>,
  ): Promise<{ created: number; deleted: string[]; retained: string[]; failures: string[] }> {
    const deleted: string[] = []
    const retained: string[] = []
    const failures: string[] = []
    for (const kind of CLEANUP_ORDER) {
      for (const resource of this.resources.filter((item) => item.kind === kind)) {
        const label = `${resource.kind}:${resource.id}:${resource.name}`
        if (resource.retain) {
          retained.push(label)
          continue
        }
        const handler = handlers[kind]
        if (!handler) {
          failures.push(`${label}: no delete handler`)
          continue
        }
        try {
          await handler(resource)
          deleted.push(label)
        } catch (error) {
          failures.push(`${label}: ${error instanceof Error ? error.message : String(error)}`)
        }
      }
    }
    return { created: this.resources.length, deleted, retained, failures }
  }
}
