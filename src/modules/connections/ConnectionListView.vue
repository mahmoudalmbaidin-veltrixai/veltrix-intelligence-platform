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
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'
import { useUiStore } from '@/shared/stores/ui'
import { safeErrorText } from '@/shared/lib/safeError'

const router = useRouter()
const platform = usePlatformStore()
const ui = useUiStore()
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
const canArchive = computed(() => platform.can('connection.archive'))
const canDelete = computed(() => platform.can('connection.delete'))
const columns = computed<Column<Connection>[]>(() => [
  { key: 'name', label: 'Connection', width: '38%' },
  { key: 'health_status', label: 'Health' },
  { key: 'credentials_configured', label: 'Credentials' },
  { key: 'last_tested_at', label: 'Last tested', align: 'right' },
  ...(canArchive.value || canDelete.value ? [{ key: 'actions', label: '', align: 'right' as const }] : []),
])

// --- Archive / delete lifecycle (both soft-archive server-side; no restore) ---
const lifecycle = ref<{ kind: 'archive' | 'delete'; row: Connection } | null>(null)
const pending = ref(false)
const errorMsg = ref<string | null>(null)

function rowMenu() {
  return [
    ...(canArchive.value ? [{ key: 'archive', label: 'Archive', icon: 'archive', danger: true }] : []),
    ...(canDelete.value ? [{ key: 'delete', label: 'Delete', icon: 'trash', danger: true }] : []),
  ]
}
function onRowMenu(row: Connection, key: string) {
  if (key === 'archive' || key === 'delete') {
    errorMsg.value = null
    lifecycle.value = { kind: key, row }
  }
}
function closeLifecycle() {
  if (pending.value) return
  lifecycle.value = null
  errorMsg.value = null
}
const lifecycleDialog = computed(() => {
  const ctx = lifecycle.value
  if (!ctx) return null
  const shared = {
    resourceName: ctx.row.name,
    impact: [
      `Type: ${ctx.row.type.name}`,
      `Current health: ${ctx.row.health_status}`,
      'Pipelines and dataset refreshes that use it may fail; schema discovery stops.',
      'Stored secret references are handled per backend policy and are never shown here.',
    ],
    note: 'Not reversible from the UI — no restore endpoint is available.',
  }
  return ctx.kind === 'archive'
    ? {
        ...shared,
        level: 'warning' as const,
        title: 'Archive connection?',
        message: 'This connection will be removed from the active connections list.',
        confirmLabel: 'Archive',
        requireTyping: false,
      }
    : {
        ...shared,
        level: 'danger' as const,
        title: 'Delete connection?',
        message: 'Delete is an elevated, audited action that removes this connection from active use.',
        confirmLabel: 'Delete',
        requireTyping: true,
      }
})
async function confirmLifecycle() {
  const ctx = lifecycle.value
  if (!ctx) return
  pending.value = true
  errorMsg.value = null
  try {
    if (ctx.kind === 'archive') await connectionService.archive(ctx.row.id)
    else await connectionService.remove(ctx.row.id)
    ui.pushToast({
      kind: 'success',
      title: ctx.kind === 'archive' ? 'Connection archived' : 'Connection deleted',
      message: ctx.row.name,
    })
    lifecycle.value = null
    await refetch()
  } catch (e) {
    errorMsg.value = safeErrorText(e)
  } finally {
    pending.value = false
  }
}
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
        <template #cell-actions="{ row }">
          <div class="connections__actions" @click.stop>
            <VipMenu :items="rowMenu()" align="end" @select="onRowMenu(row, $event)">
              <template #trigger>
                <button class="connections__menu" :aria-label="`Actions for ${row.name}`">
                  <VipIcon name="dotsV" :size="16" />
                </button>
              </template>
            </VipMenu>
          </div>
        </template>
      </VipTable>
    </VipCard>

    <VipConfirmDialog
      v-if="lifecycleDialog"
      :open="!!lifecycle"
      :level="lifecycleDialog.level"
      :title="lifecycleDialog.title"
      :resource-name="lifecycleDialog.resourceName"
      :message="lifecycleDialog.message"
      :impact="lifecycleDialog.impact"
      :note="lifecycleDialog.note"
      :confirm-label="lifecycleDialog.confirmLabel"
      :require-typing="lifecycleDialog.requireTyping"
      :pending="pending"
      :error="errorMsg"
      @confirm="confirmLifecycle"
      @cancel="closeLifecycle"
    />
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
.connections__actions {
  display: flex;
  justify-content: flex-end;
}
.connections__menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--vip-text-secondary);
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-md);
}
.connections__menu:hover {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border);
  color: var(--vip-text-primary);
}
</style>
