<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { usePlatformStore } from '@/shared/stores/platform'
import { relativeTime } from '@/shared/lib/format'
import {
  connectionService,
  CONNECTOR_ICON,
  CONNECTOR_LABEL,
  type Connection,
  type ConnectionStatus,
} from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const router = useRouter()
const platform = usePlatformStore()

const { data, isLoading } = useQuery('connections:list', (signal) =>
  connectionService.list().then((r) => {
    signal.throwIfAborted()
    return r
  }),
)

const search = ref('')

const rows = computed<Connection[]>(() => {
  const all = data.value ?? []
  const q = search.value.trim().toLowerCase()
  if (!q) return all
  return all.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.owner.toLowerCase().includes(q) ||
      CONNECTOR_LABEL[c.connector].toLowerCase().includes(q) ||
      (c.host?.toLowerCase().includes(q) ?? false),
  )
})

const STATUS_TONE: Record<ConnectionStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  healthy: 'success',
  degraded: 'warning',
  error: 'danger',
  configuring: 'info',
}
const STATUS_LABEL: Record<ConnectionStatus, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  error: 'Error',
  configuring: 'Configuring',
}

const columns: Column<Connection>[] = [
  { key: 'name', label: 'Connection', width: '34%' },
  { key: 'status', label: 'Status' },
  { key: 'owner', label: 'Owner' },
  { key: 'host', label: 'Host / endpoint' },
  { key: 'lastTested', label: 'Last tested', align: 'right' },
]

function openConnection(row: Connection) {
  router.push(`/connections/${row.id}`)
}
</script>

<template>
  <div class="conn-list">
    <VipPageHeader
      title="Connections"
      description="Manage the data sources feeding pipelines, datasets and semantic models."
    >
      <template #actions>
        <VipButton
          v-if="platform.can('connection:write')"
          variant="tertiary"
          icon="store"
          @click="router.push('/connections/catalog')"
        >
          Browse connectors
        </VipButton>
        <VipButton
          v-if="platform.can('connection:write')"
          variant="primary"
          icon="plus"
          @click="router.push('/connections/new')"
        >
          New connection
        </VipButton>
      </template>
    </VipPageHeader>

    <VipCard :padded="false">
      <div class="conn-list__toolbar">
        <div class="conn-list__search">
          <VipInput
            v-model="search"
            icon="search"
            size="sm"
            placeholder="Search by name, owner, connector or host"
          />
        </div>
        <span class="conn-list__count">
          {{ rows.length }} {{ rows.length === 1 ? 'connection' : 'connections' }}
        </span>
      </div>

      <VipTable
        :columns="columns"
        :rows="rows"
        :row-key="(r) => r.id"
        :loading="isLoading"
        clickable
        density="comfortable"
        empty-title="No connections found"
        empty-description="Try a different search, or create a new connection to get started."
        @row-click="openConnection"
      >
        <template #cell-name="{ row }">
          <div class="conn-list__name">
            <span class="conn-list__icon">
              <VipIcon :name="CONNECTOR_ICON[row.connector]" :size="16" />
            </span>
            <div class="conn-list__name-text">
              <span class="conn-list__title">{{ row.name }}</span>
              <span class="conn-list__connector">{{ CONNECTOR_LABEL[row.connector] }}</span>
            </div>
          </div>
        </template>

        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">
            {{ STATUS_LABEL[row.status] }}
          </VipBadge>
        </template>

        <template #cell-host="{ row }">
          <span class="conn-list__host">{{ row.host ?? '—' }}</span>
        </template>

        <template #cell-lastTested="{ row }">
          <span class="conn-list__muted">{{ relativeTime(row.lastTested) }}</span>
        </template>
      </VipTable>
    </VipCard>
  </div>
</template>

<style scoped>
.conn-list { max-width: 1280px; margin: 0 auto; }
.conn-list__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.conn-list__search { width: min(360px, 100%); }
.conn-list__count { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); white-space: nowrap; }
.conn-list__name { display: flex; align-items: center; gap: var(--vip-sp-5); }
.conn-list__icon {
  width: 32px; height: 32px; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.conn-list__name-text { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.conn-list__title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.conn-list__connector { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.conn-list__host { font-family: var(--vip-font-mono); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
.conn-list__muted { color: var(--vip-text-muted); }
</style>
