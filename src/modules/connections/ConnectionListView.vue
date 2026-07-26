<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { usePlatformStore } from '@/shared/stores/platform'
import { relativeTime } from '@/shared/lib/format'
import { connectionIcon, connectionService, type Connection, type ConnectionHealth } from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const router = useRouter()
const platform = usePlatformStore()
const search = ref('')
const tenantKey = computed(() => `${platform.organization?.id ?? 'none'}:${platform.workspace?.id ?? 'none'}`)
const { data, isLoading, error, refetch } = useQuery(
  () => `connections:${tenantKey.value}:list`,
  () => connectionService.list(),
)
const rows = computed(() => {
  const query = search.value.trim().toLowerCase()
  return (data.value?.items ?? []).filter(
    (item) => !query || item.name.toLowerCase().includes(query) || item.type.name.toLowerCase().includes(query),
  )
})
const tones: Record<ConnectionHealth, 'success' | 'warning' | 'danger' | 'neutral' | 'info'> = {
  healthy: 'success',
  degraded: 'warning',
  unhealthy: 'danger',
  unknown: 'neutral',
  testing: 'info',
}
const columns: Column<Connection>[] = [
  { key: 'name', label: 'Connection', width: '38%' },
  { key: 'health_status', label: 'Health' },
  { key: 'credentials_configured', label: 'Credentials' },
  { key: 'last_tested_at', label: 'Last tested', align: 'right' },
]
</script>

<template>
  <div class="connections">
    <VipPageHeader title="Connections" description="Securely manage this workspace's external systems.">
      <template #actions>
        <VipButton
          v-if="platform.can('connection.types.read')"
          variant="tertiary"
          icon="store"
          @click="router.push('/connections/catalog')"
          >Connector catalog</VipButton
        >
        <VipButton
          v-if="platform.can('connection.create')"
          variant="primary"
          icon="plus"
          @click="router.push('/connections/new')"
          >New connection</VipButton
        >
      </template>
    </VipPageHeader>
    <VipCard :padded="false">
      <div class="connections__toolbar">
        <VipInput v-model="search" icon="search" size="sm" placeholder="Search connections" />
        <span>{{ rows.length }} connections</span>
        <VipButton variant="ghost" size="xs" icon="refresh" :loading="isLoading" @click="refetch"
          >Refresh health</VipButton
        >
      </div>
      <div v-if="error" class="connections__error" role="alert">
        <span>Connections could not be loaded.</span>
        <VipButton variant="ghost" size="xs" @click="refetch">Retry</VipButton>
      </div>
      <VipTable
        :columns="columns"
        :rows="rows"
        :row-key="(row) => row.id"
        :loading="isLoading"
        clickable
        empty-title="No connections"
        empty-description="Create a connection to get started."
        @row-click="(row) => router.push(`/connections/${row.id}`)"
      >
        <template #cell-name="{ row }"
          ><span class="connections__name"
            ><VipIcon :name="connectionIcon(row.type.key)" :size="16" /><span
              ><strong>{{ row.name }}</strong
              ><small>{{ row.type.name }}</small></span
            ></span
          ></template
        >
        <template #cell-health_status="{ row }"
          ><VipBadge :tone="tones[row.health_status]" variant="soft" size="sm">{{
            row.health_status
          }}</VipBadge></template
        >
        <template #cell-credentials_configured="{ row }">{{
          row.credentials_configured ? 'Configured' : 'Not configured'
        }}</template>
        <template #cell-last_tested_at="{ row }">{{
          row.last_tested_at ? relativeTime(row.last_tested_at) : 'Never'
        }}</template>
      </VipTable>
    </VipCard>
  </div>
</template>

<style scoped>
.connections {
  max-width: 1280px;
  margin: 0 auto;
}
.connections__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
  color: var(--vip-text-muted);
}
.connections__toolbar > *:first-child {
  width: min(360px, 100%);
}
.connections__name {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.connections__name span {
  display: flex;
  flex-direction: column;
}
.connections__name small {
  color: var(--vip-text-muted);
}
.connections__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-5);
  color: var(--vip-danger-text);
}
</style>
