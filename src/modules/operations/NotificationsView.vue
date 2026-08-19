<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { settingsService } from '@/modules/settings/settings.service'
import { relativeTime } from '@/shared/lib/format'
import { operationsService, type Notification, type Severity } from './operations.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'

const router = useRouter()
const ui = useUiStore()

const { data, isLoading } = useQuery('operations:notifications', (signal) =>
  operationsService.listNotifications().then((r) => {
    signal.throwIfAborted()
    return r
  }),
)

const items = ref<Notification[]>([])
watch(
  data,
  (d) => {
    if (d) items.value = d.map((n) => ({ ...n }))
  },
  { immediate: true },
)
const list = computed<Notification[]>(() => items.value)

const SEVERITY_TONE: Record<Severity, 'info' | 'success' | 'warning' | 'danger'> = {
  info: 'info',
  success: 'success',
  warning: 'warning',
  danger: 'danger',
}
const SEVERITY_ICON: Record<Severity, string> = {
  info: 'info',
  success: 'success',
  warning: 'warning',
  danger: 'error',
}

type SeverityFilter = 'all' | Severity
const severityFilter = ref<SeverityFilter>('all')
const severityOptions: { value: SeverityFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'danger', label: 'Critical' },
  { value: 'warning', label: 'Warning' },
  { value: 'success', label: 'Success' },
  { value: 'info', label: 'Info' },
]

type ReadFilter = 'all' | 'unread' | 'read'
const readFilter = ref<ReadFilter>('all')
const readOptions: { value: ReadFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread' },
  { value: 'read', label: 'Read' },
]

const activeCategory = ref('all')
const categories = computed(() => {
  const set = new Map<string, number>()
  for (const n of list.value) set.set(n.category, (set.get(n.category) ?? 0) + 1)
  return [...set.entries()].map(([value, count]) => ({ value, label: value, count }))
})
const tabs = computed(() => [{ value: 'all', label: 'All', count: list.value.length }, ...categories.value])

const filtered = computed(() =>
  list.value.filter((n) => {
    if (severityFilter.value !== 'all' && n.severity !== severityFilter.value) return false
    if (readFilter.value === 'unread' && n.read) return false
    if (readFilter.value === 'read' && !n.read) return false
    if (activeCategory.value !== 'all' && n.category !== activeCategory.value) return false
    return true
  }),
)

const unreadCount = computed(() => list.value.filter((n) => !n.read).length)

async function markRead(n: Notification) {
  try {
    ui.unreadNotifications = await operationsService.markNotificationRead(n.id)
    n.read = true
  } catch {
    n.read = true
    ui.unreadNotifications = unreadCount.value
  }
}
async function markUnread(n: Notification) {
  try {
    ui.unreadNotifications = await operationsService.markNotificationUnread(n.id)
    n.read = false
  } catch {
    n.read = false
    ui.unreadNotifications = unreadCount.value
  }
}
async function markAllRead() {
  try {
    ui.unreadNotifications = await operationsService.markAllNotificationsRead()
    items.value.forEach((n) => (n.read = true))
    ui.pushToast({ kind: 'success', title: 'All notifications marked as read' })
  } catch (cause) {
    ui.pushToast({
      kind: 'error',
      title: 'Could not mark all as read',
      message: (cause as Error).message,
    })
  }
}
function archive(n: Notification) {
  items.value = items.value.filter((x) => x.id !== n.id)
  ui.unreadNotifications = unreadCount.value
  ui.pushToast({ kind: 'info', title: 'Notification archived', message: n.title })
}
async function openResource(n: Notification) {
  if (!n.resource) return
  await markRead(n)
  router.push(n.resource.to)
}

// ------- Notification preferences (persisted per-user) ------- //
const platform = usePlatformStore()
// Only categories for modules that actually exist in V1. Gated modules
// (Reports, Billing, Marketplace, Developer, Automation) are intentionally not
// offered here so the preferences list never implies a capability the customer
// cannot use. Previously-saved values for other keys are preserved in the bag.
const PREF_DEFAULTS: Record<string, boolean> = {
  Pipelines: true,
  Datasets: true,
  Dashboards: true,
  System: true,
}
const preferences = reactive<Record<string, boolean>>({ ...PREF_DEFAULTS })
const prefKeys = Object.keys(preferences)
const savingPreferences = ref(false)

/** Hydrate from the user's persisted preferences (defaults never overwrite them). */
function loadPreferences() {
  const stored = platform.user.preferences?.notifications
  if (stored && typeof stored === 'object') {
    for (const key of prefKeys) {
      const value = (stored as Record<string, unknown>)[key]
      if (typeof value === 'boolean') preferences[key] = value
    }
  }
}
onMounted(loadPreferences)
// Re-hydrate if the user changes (e.g., re-login) so saved values reappear.
watch(() => platform.user.id, loadPreferences)

async function savePreferences() {
  if (savingPreferences.value) return
  savingPreferences.value = true
  try {
    const session = await settingsService.updatePreferences({ notifications: { ...preferences } })
    platform.hydrateAuthenticatedUser(session.user)
    ui.pushToast({ kind: 'success', title: 'Notification preferences saved' })
  } catch (cause) {
    ui.pushToast({
      kind: 'error',
      title: 'Unable to save notification preferences',
      message: (cause as Error).message || 'Please try again.',
    })
  } finally {
    savingPreferences.value = false
  }
}
</script>

<template>
  <div class="ntf">
    <VipPageHeader
      title="Notifications"
      description="Operational alerts across pipelines, governance, billing and the platform."
    >
      <template #status>
        <VipBadge v-if="unreadCount" tone="brand" variant="soft" size="sm"> {{ unreadCount }} unread </VipBadge>
      </template>
      <template #actions>
        <VipButton variant="tertiary" icon="check" :disabled="!unreadCount" @click="markAllRead">
          Mark all read
        </VipButton>
      </template>
      <template #tabs>
        <VipTabs v-model="activeCategory" :tabs="tabs" />
      </template>
    </VipPageHeader>

    <div class="ntf__layout">
      <div class="ntf__main">
        <div class="ntf__filters">
          <VipSegmented v-model="severityFilter" :options="severityOptions" size="sm" />
          <VipSegmented v-model="readFilter" :options="readOptions" size="sm" />
        </div>

        <VipCard :padded="false">
          <div v-if="isLoading" class="ntf__loading">
            <VipSkeleton v-for="i in 5" :key="i" height="64px" block />
          </div>
          <VipEmptyState
            v-else-if="!filtered.length"
            icon="bell"
            title="Nothing here"
            description="No notifications match the current filters."
          />
          <ul v-else class="ntf__list">
            <li v-for="n in filtered" :key="n.id" class="ntf__item" :class="{ 'is-unread': !n.read }">
              <span class="ntf__dot" :class="`is-${n.severity}`">
                <VipIcon :name="SEVERITY_ICON[n.severity]" :size="15" />
              </span>
              <div class="ntf__body">
                <div class="ntf__row">
                  <span class="ntf__title">{{ n.title }}</span>
                  <VipBadge :tone="SEVERITY_TONE[n.severity]" variant="soft" size="sm">
                    {{ n.category }}
                  </VipBadge>
                  <span class="ntf__time">{{ relativeTime(n.ts) }}</span>
                </div>
                <p class="ntf__text">{{ n.body }}</p>
                <div class="ntf__actions">
                  <VipButton
                    v-if="n.resource"
                    variant="ghost"
                    size="xs"
                    icon-right="chevronRight"
                    @click="openResource(n)"
                  >
                    {{ n.resource.label }}
                  </VipButton>
                  <VipButton v-if="!n.read" variant="ghost" size="xs" icon="check" @click="markRead(n)">
                    Mark read
                  </VipButton>
                  <VipButton v-else variant="ghost" size="xs" icon="undo" @click="markUnread(n)">
                    Mark unread
                  </VipButton>
                  <VipButton variant="ghost" size="xs" icon="trash" @click="archive(n)"> Archive </VipButton>
                </div>
              </div>
            </li>
          </ul>
        </VipCard>
      </div>

      <aside class="ntf__side">
        <VipCard>
          <div class="ntf__pref-head">
            <h2 class="ntf__pref-title">Notification preferences</h2>
            <p class="ntf__pref-desc">Choose which categories deliver alerts to you.</p>
          </div>
          <ul class="ntf__pref-list">
            <li v-for="key in prefKeys" :key="key" class="ntf__pref-row">
              <span class="ntf__pref-label">{{ key }}</span>
              <VipSwitch v-model="preferences[key]" size="sm" />
            </li>
          </ul>
          <VipButton
            variant="secondary"
            size="sm"
            block
            :loading="savingPreferences"
            :disabled="savingPreferences"
            @click="savePreferences"
          >
            Save preferences
          </VipButton>
        </VipCard>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.ntf {
  max-width: 1280px;
  margin: 0 auto;
}
.ntf__layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--vip-sp-6);
  align-items: start;
}
.ntf__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.ntf__filters {
  display: flex;
  gap: var(--vip-sp-4);
  flex-wrap: wrap;
}
.ntf__loading {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-5);
}
.ntf__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.ntf__item {
  display: flex;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.ntf__item:last-child {
  border-bottom: none;
}
.ntf__item.is-unread {
  background: var(--vip-surface-2);
}
.ntf__dot {
  width: 32px;
  height: 32px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
}
.ntf__dot.is-info {
  background: var(--vip-info-soft);
  color: var(--vip-info-text);
}
.ntf__dot.is-success {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.ntf__dot.is-warning {
  background: var(--vip-warning-soft);
  color: var(--vip-warning-text);
}
.ntf__dot.is-danger {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.ntf__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.ntf__row {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  flex-wrap: wrap;
}
.ntf__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.ntf__time {
  margin-left: auto;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.ntf__text {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin: 0;
}
.ntf__actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  flex-wrap: wrap;
  margin-top: var(--vip-sp-2);
}
.ntf__side {
  position: sticky;
  top: var(--vip-sp-6);
}
.ntf__pref-head {
  margin-bottom: var(--vip-sp-5);
}
.ntf__pref-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.ntf__pref-desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-2);
}
.ntf__pref-list {
  list-style: none;
  margin: 0 0 var(--vip-sp-5);
  padding: 0;
  display: flex;
  flex-direction: column;
}
.ntf__pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.ntf__pref-row:last-child {
  border-bottom: none;
}
.ntf__pref-label {
  font-size: var(--vip-fs-md);
  color: var(--vip-text-secondary);
}
@media (max-width: 960px) {
  .ntf__layout {
    grid-template-columns: 1fr;
  }
  .ntf__side {
    position: static;
  }
}
</style>
