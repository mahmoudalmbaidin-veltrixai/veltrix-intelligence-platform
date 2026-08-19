<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { dashboardService } from './dashboards.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'
import { safeErrorText } from '@/shared/lib/safeError'

const router = useRouter()
const platform = usePlatformStore()
const ui = useUiStore()
const { data, isLoading, refetch } = useQuery('dashboards:list', () => dashboardService.list())

type DashboardRow = NonNullable<typeof data.value>[number]

// --- Lifecycle confirmation state (archive / delete) ---
const lifecycle = ref<{ kind: 'archive' | 'delete'; row: DashboardRow } | null>(null)
const lifecyclePending = ref(false)
const lifecycleError = ref<string | null>(null)

function openLifecycle(kind: 'archive' | 'delete', row: DashboardRow) {
  lifecycleError.value = null
  lifecycle.value = { kind, row }
}
function closeLifecycle() {
  if (lifecyclePending.value) return
  lifecycle.value = null
  lifecycleError.value = null
}

const lifecycleDialog = computed(() => {
  const ctx = lifecycle.value
  if (!ctx) return null
  const { kind, row } = ctx
  if (kind === 'archive') {
    return {
      level: 'warning' as const,
      title: 'Archive dashboard?',
      resourceName: row.name,
      message: 'This dashboard will be removed from all active dashboard lists.',
      impact: [
        `Current status: ${row.status}`,
        'Published links and scheduled deliveries may stop working, per backend lifecycle rules.',
        'Archived dashboards are not listed and cannot be restored from the app in this release.',
      ],
      note: 'Archiving is not reversible from the UI — no restore endpoint is available.',
      confirmLabel: 'Archive',
      requireTyping: false,
    }
  }
  return {
    level: 'danger' as const,
    title: 'Delete dashboard?',
    resourceName: row.name,
    message: 'Delete is an elevated, audited action that removes this dashboard from all active lists.',
    impact: [
      `${row.pageCount} page(s) and ${row.widgetCount} visual(s) will no longer be accessible`,
      `Current status: ${row.status}`,
      'Published links, scheduled deliveries and exports referencing it may be affected.',
    ],
    note: 'The server soft-archives on delete; there is no in-app restore, so treat this as final.',
    confirmLabel: 'Delete',
    requireTyping: true,
  }
})

async function confirmLifecycle() {
  const ctx = lifecycle.value
  if (!ctx) return
  lifecyclePending.value = true
  lifecycleError.value = null
  try {
    const version = await dashboardService.rowVersion(ctx.row.id)
    await dashboardService[ctx.kind](ctx.row.id, version)
    ui.pushToast({
      kind: 'success',
      title: ctx.kind === 'delete' ? 'Dashboard deleted' : 'Dashboard archived',
      message: ctx.row.name,
    })
    lifecycle.value = null
    await refetch()
  } catch (error) {
    // Keep the dialog open and surface the backend-provided reason (409, etc.).
    lifecycleError.value = safeErrorText(error)
  } finally {
    lifecyclePending.value = false
  }
}

const route = useRoute()
const search = ref('')
const filter = ref<'all' | 'favorites' | 'published'>(route.name === 'dashboards-published' ? 'published' : 'all')

const items = computed(() => {
  let list = data.value ?? []
  if (filter.value === 'favorites') list = list.filter((d) => d.favorite)
  if (filter.value === 'published') list = list.filter((d) => d.status === 'published')
  const q = search.value.trim().toLowerCase()
  if (q) list = list.filter((d) => d.name.toLowerCase().includes(q) || d.tags.some((t) => t.includes(q)))
  return list
})

function menuFor() {
  return [
    ...(platform.can('dashboard.update')
      ? [
          { key: 'rename', label: 'Rename', icon: 'edit' },
          { key: 'duplicate', label: 'Duplicate', icon: 'duplicate' },
        ]
      : []),
    ...(platform.can('dashboard.archive')
      ? [
          { key: 'divider', label: '', divider: true },
          { key: 'archive', label: 'Archive', icon: 'archive', danger: true },
        ]
      : []),
    ...(platform.can('dashboard.delete') ? [{ key: 'delete', label: 'Delete', icon: 'trash', danger: true }] : []),
  ]
}
async function onMenu(dashboard: (typeof items.value)[number], key: string) {
  try {
    if (key === 'rename') {
      const name = window.prompt('Dashboard name', dashboard.name)?.trim()
      if (!name || name === dashboard.name) return
      await dashboardService.rename(dashboard.id, name)
      ui.pushToast({ kind: 'success', title: 'Dashboard renamed' })
    } else if (key === 'duplicate') {
      const copy = await dashboardService.duplicate(dashboard.id)
      ui.pushToast({ kind: 'success', title: 'Dashboard duplicated' })
      await router.push(`/dashboards/${copy.id}/edit`)
      return
    } else if (key === 'archive' || key === 'delete') {
      openLifecycle(key, dashboard)
      return
    }
    await refetch()
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Dashboard action failed', message: safeErrorText(error) })
  }
}
</script>

<template>
  <div>
    <VipPageHeader title="Dashboards" description="Explore and author interactive analytics dashboards.">
      <template #actions>
        <VipButton variant="tertiary" icon="calendar" @click="router.push('/dashboards/deliveries')"
          >Deliveries</VipButton
        >
        <VipButton
          v-if="platform.can('dashboard.create')"
          variant="primary"
          icon="plus"
          @click="router.push('/dashboards/new')"
          >New dashboard</VipButton
        >
      </template>
    </VipPageHeader>

    <div class="dl-toolbar">
      <VipInput v-model="search" icon="search" placeholder="Search dashboards…" size="sm" />
      <VipSegmented
        v-model="filter"
        :options="[
          { value: 'all', label: 'All' },
          { value: 'favorites', label: 'Favorites' },
          { value: 'published', label: 'Published' },
        ]"
        size="sm"
      />
    </div>

    <div v-if="isLoading" class="dl-grid">
      <VipCard v-for="n in 6" :key="n"
        ><VipSkeleton height="120px" block /><VipSkeleton width="60%" style="margin-top: 12px"
      /></VipCard>
    </div>
    <div v-else class="dl-grid">
      <VipCard
        v-for="d in items"
        :key="d.id"
        hoverable
        :padded="false"
        class="dl-card"
        @click="router.push(`/dashboards/${d.id}`)"
      >
        <div class="dl-thumb">
          <VipIcon name="chart" :size="30" />
          <VipIcon v-if="d.favorite" name="star" :size="15" class="dl-fav" />
          <div v-if="menuFor().length" class="dl-actions" @click.stop>
            <VipMenu :items="menuFor()" align="end" @select="onMenu(d, $event)">
              <template #trigger>
                <button class="dl-menu" :aria-label="`Actions for ${d.name}`">
                  <VipIcon name="dotsV" :size="16" />
                </button>
              </template>
            </VipMenu>
          </div>
        </div>
        <div class="dl-info">
          <div class="dl-name">{{ d.name }}</div>
          <div class="dl-meta">
            <VipBadge :tone="d.status === 'published' ? 'success' : 'neutral'" size="sm">{{ d.status }}</VipBadge>
            <span class="dl-muted">{{ d.pageCount }} pages · {{ d.widgetCount }} visuals</span>
          </div>
          <div class="dl-foot">{{ d.owner }} · {{ relativeTime(d.updatedAt) }}</div>
        </div>
      </VipCard>
    </div>

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
      :pending="lifecyclePending"
      :error="lifecycleError"
      @confirm="confirmLifecycle"
      @cancel="closeLifecycle"
    />
  </div>
</template>

<style scoped>
.dl-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-6);
  flex-wrap: wrap;
}
.dl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--vip-sp-6);
}
.dl-card {
  overflow: hidden;
}
.dl-thumb {
  position: relative;
  height: 130px;
  background: linear-gradient(135deg, var(--vip-surface-2), var(--vip-surface-3));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--vip-text-disabled);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.dl-fav {
  position: absolute;
  top: var(--vip-sp-4);
  right: var(--vip-sp-4);
  color: var(--vip-warning);
}
.dl-actions {
  position: absolute;
  top: var(--vip-sp-3);
  left: var(--vip-sp-3);
}
.dl-menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  color: var(--vip-text-secondary);
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.dl-info {
  padding: var(--vip-sp-5);
}
.dl-name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.dl-meta {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  margin-top: var(--vip-sp-3);
}
.dl-muted {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.dl-foot {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
  margin-top: var(--vip-sp-3);
}
</style>
