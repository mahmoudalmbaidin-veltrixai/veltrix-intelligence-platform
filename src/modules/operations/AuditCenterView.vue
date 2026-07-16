<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime, formatDateTime } from '@/shared/lib/format'
import { operationsService, type AuditEvent, type AuditResult } from './operations.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()

const { data, isLoading } = useQuery('operations:audit', (signal) =>
  operationsService.listAudit().then((r) => {
    signal.throwIfAborted()
    return r
  }),
)

const search = ref('')
const actorFilter = ref('')
const resultFilter = ref<AuditResult | 'all'>('all')
const fromDate = ref('')
const toDate = ref('')

const events = computed<AuditEvent[]>(() => data.value ?? [])

const actorOptions = computed(() => {
  const set = new Set(events.value.map((e) => e.actor))
  return [{ value: '', label: 'All actors' }, ...[...set].map((a) => ({ value: a, label: a }))]
})
const resultOptions: { value: AuditResult | 'all'; label: string }[] = [
  { value: 'all', label: 'All results' },
  { value: 'success', label: 'Success' },
  { value: 'denied', label: 'Denied' },
  { value: 'error', label: 'Error' },
]

const rows = computed<AuditEvent[]>(() =>
  events.value.filter((e) => {
    if (actorFilter.value && e.actor !== actorFilter.value) return false
    if (resultFilter.value !== 'all' && e.result !== resultFilter.value) return false
    if (fromDate.value && new Date(e.ts).getTime() < new Date(fromDate.value).getTime()) return false
    if (toDate.value && new Date(e.ts).getTime() > new Date(toDate.value).getTime() + 86_400_000) return false
    const q = search.value.trim().toLowerCase()
    if (q) {
      const hit =
        e.actor.toLowerCase().includes(q) ||
        e.action.toLowerCase().includes(q) ||
        e.resource.toLowerCase().includes(q) ||
        e.correlationId.toLowerCase().includes(q)
      if (!hit) return false
    }
    return true
  }),
)

const RESULT_TONE: Record<AuditResult, 'success' | 'warning' | 'danger'> = {
  success: 'success',
  denied: 'warning',
  error: 'danger',
}

const columns: Column<AuditEvent>[] = [
  { key: 'actor', label: 'Actor', width: '22%' },
  { key: 'action', label: 'Action' },
  { key: 'resource', label: 'Resource' },
  { key: 'result', label: 'Result' },
  { key: 'ip', label: 'IP address' },
  { key: 'ts', label: 'Timestamp', align: 'right' },
]

const selected = ref<AuditEvent | null>(null)
function openDetail(row: AuditEvent) {
  selected.value = row
}
function closeDetail() {
  selected.value = null
}

function exportLog() {
  ui.pushToast({
    kind: 'info',
    title: 'Export queued',
    message: `Exporting ${rows.value.length} audit events to CSV. This is a backend dependency.`,
  })
}

function pretty(value: Record<string, unknown> | undefined): string {
  if (!value) return '—'
  return JSON.stringify(value, null, 2)
}
</script>

<template>
  <div class="aud">
    <VipPageHeader
      title="Audit log"
      description="Immutable record of security-relevant actions across the organization."
    >
      <template #actions>
        <VipButton variant="tertiary" icon="download" @click="exportLog">Export</VipButton>
      </template>
    </VipPageHeader>

    <VipCard :padded="false">
      <div class="aud__toolbar">
        <div class="aud__search">
          <VipInput
            v-model="search"
            icon="search"
            size="sm"
            placeholder="Search actor, action, resource or correlation ID"
          />
        </div>
        <div class="aud__filters">
          <VipSelect v-model="actorFilter" :options="actorOptions" size="sm" />
          <VipSelect v-model="resultFilter" :options="resultOptions" size="sm" />
          <VipInput v-model="fromDate" type="date" size="sm" />
          <VipInput v-model="toDate" type="date" size="sm" />
        </div>
      </div>

      <VipTable
        :columns="columns"
        :rows="rows"
        :row-key="(r) => r.id"
        :loading="isLoading"
        clickable
        density="compact"
        empty-title="No audit events"
        empty-description="Adjust the search or filters to see more events."
        @row-click="openDetail"
      >
        <template #cell-actor="{ row }">
          <span class="aud__actor">{{ row.actor }}</span>
        </template>
        <template #cell-action="{ row }">
          <code class="aud__code">{{ row.action }}</code>
        </template>
        <template #cell-resource="{ row }">
          <code class="aud__code">{{ row.resource }}</code>
        </template>
        <template #cell-result="{ row }">
          <VipBadge :tone="RESULT_TONE[row.result]" variant="soft" size="sm">
            {{ row.result }}
          </VipBadge>
        </template>
        <template #cell-ip="{ row }">
          <span class="aud__ip">{{ row.ip }}</span>
        </template>
        <template #cell-ts="{ row }">
          <span class="aud__muted" :title="formatDateTime(row.ts)">{{ relativeTime(row.ts) }}</span>
        </template>
      </VipTable>
    </VipCard>

    <VipDrawer
      :open="!!selected"
      :title="selected ? selected.action : 'Audit event'"
      :width="520"
      @close="closeDetail"
    >
      <div v-if="selected" class="aud__detail">
        <VipAlert tone="info" title="Sensitive fields redacted">
          Credentials, tokens and secrets are automatically redacted from before/after
          snapshots and never stored in the audit trail.
        </VipAlert>

        <dl class="aud__dl">
          <div class="aud__dl-row">
            <dt>Result</dt>
            <dd>
              <VipBadge :tone="RESULT_TONE[selected.result]" variant="soft" size="sm">
                {{ selected.result }}
              </VipBadge>
            </dd>
          </div>
          <div class="aud__dl-row"><dt>Actor</dt><dd>{{ selected.actor }}</dd></div>
          <div class="aud__dl-row"><dt>Action</dt><dd><code class="aud__code">{{ selected.action }}</code></dd></div>
          <div class="aud__dl-row"><dt>Resource</dt><dd><code class="aud__code">{{ selected.resource }}</code></dd></div>
          <div class="aud__dl-row"><dt>Workspace</dt><dd>{{ selected.workspace }}</dd></div>
          <div class="aud__dl-row"><dt>Organization</dt><dd>{{ selected.org }}</dd></div>
          <div class="aud__dl-row"><dt>IP address</dt><dd>{{ selected.ip }}</dd></div>
          <div class="aud__dl-row"><dt>Timestamp</dt><dd>{{ formatDateTime(selected.ts) }}</dd></div>
          <div class="aud__dl-row">
            <dt>Correlation ID</dt>
            <dd><code class="aud__code">{{ selected.correlationId }}</code></dd>
          </div>
        </dl>

        <div class="aud__diff">
          <div class="aud__diff-col">
            <h3 class="aud__diff-title">Before</h3>
            <pre class="aud__json">{{ pretty(selected.before) }}</pre>
          </div>
          <div class="aud__diff-col">
            <h3 class="aud__diff-title">After</h3>
            <pre class="aud__json">{{ pretty(selected.after) }}</pre>
          </div>
        </div>
      </div>

      <template #footer>
        <VipButton variant="secondary" @click="closeDetail">Close</VipButton>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.aud { max-width: 1280px; margin: 0 auto; }
.aud__toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--vip-sp-5); flex-wrap: wrap;
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.aud__search { width: min(360px, 100%); }
.aud__filters { display: flex; gap: var(--vip-sp-4); flex-wrap: wrap; }
.aud__actor { font-size: var(--vip-fs-sm); color: var(--vip-text-primary); }
.aud__code { font-family: var(--vip-font-mono); font-size: var(--vip-fs-xs); color: var(--vip-text-secondary); }
.aud__ip { font-family: var(--vip-font-mono); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.aud__muted { color: var(--vip-text-muted); }
.aud__detail { display: flex; flex-direction: column; gap: var(--vip-sp-6); }
.aud__dl { display: flex; flex-direction: column; gap: 0; margin: 0; }
.aud__dl-row {
  display: flex; align-items: center; gap: var(--vip-sp-5);
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.aud__dl-row dt { flex: none; width: 120px; font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.aud__dl-row dd { margin: 0; font-size: var(--vip-fs-sm); color: var(--vip-text-primary); }
.aud__diff { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-4); }
.aud__diff-title { font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); margin-bottom: var(--vip-sp-3); }
.aud__json {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-2xs);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-4);
  margin: 0;
  overflow-x: auto;
  color: var(--vip-text-secondary);
  white-space: pre-wrap;
}
</style>
