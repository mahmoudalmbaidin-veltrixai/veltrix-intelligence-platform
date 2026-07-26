import { effectScope, nextTick, ref } from 'vue'
import { describe, expect, it } from 'vitest'
import { useQuery } from './query'

describe('useQuery context changes', () => {
  it('aborts the previous request and ignores its stale result when the scoped key changes', async () => {
    const scopeKey = ref('tenant-a:workspace-a')
    const pending = new Map<string, { signal: AbortSignal; resolve: (value: string) => void }>()
    const scope = effectScope()
    const query = scope.run(() =>
      useQuery(
        () => `isolation:${scopeKey.value}`,
        (signal) =>
          new Promise<string>((resolve) => {
            pending.set(scopeKey.value, { signal, resolve })
          }),
        { retry: 0 },
      ),
    )!

    await nextTick()
    const tenantA = pending.get('tenant-a:workspace-a')!
    scopeKey.value = 'tenant-b:workspace-b'
    await nextTick()
    const tenantB = pending.get('tenant-b:workspace-b')!

    expect(tenantA.signal.aborted).toBe(true)
    tenantA.resolve('stale tenant A data')
    tenantB.resolve('tenant B data')
    await Promise.resolve()
    await nextTick()

    expect(query.data.value).toBe('tenant B data')
    scope.stop()
  })
})
