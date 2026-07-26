<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import { operationsService, type Notification } from '@/modules/operations/operations.service'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const ui = useUiStore()
const router = useRouter()

const items = ref<Notification[]>([])
const loading = ref(false)
const loadError = ref('')
const unread = computed(() => items.value.filter((item) => !item.read).length)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    items.value = await operationsService.listNotifications()
    ui.unreadNotifications = unread.value
  } catch (cause) {
    loadError.value = (cause as Error).message
  } finally {
    loading.value = false
  }
}

watch(
  () => ui.notificationDrawerOpen,
  (open) => {
    if (open) void load()
  },
  { immediate: true },
)

function markAll() {
  items.value = items.value.map((n) => ({ ...n, read: true }))
  ui.unreadNotifications = 0
}
function open(n: Notification) {
  n.read = true
  ui.unreadNotifications = items.value.filter((x) => !x.read).length
  ui.notificationDrawerOpen = false
  if (n.resource) router.push(n.resource.to)
}
</script>

<template>
  <VipDrawer
    :open="ui.notificationDrawerOpen"
    title="Notifications"
    :width="420"
    @close="ui.notificationDrawerOpen = false"
  >
    <template #default>
      <div class="ndrawer__toolbar">
        <VipButton variant="ghost" size="sm" icon="check" @click="markAll">Mark all read</VipButton>
        <VipButton
          variant="ghost"
          size="sm"
          icon="external"
          @click="((ui.notificationDrawerOpen = false), router.push('/notifications'))"
          >Open center</VipButton
        >
      </div>
      <p v-if="loading" role="status">Loading notifications…</p>
      <p v-else-if="loadError" role="alert">
        {{ loadError }} <VipButton variant="ghost" size="sm" @click="load">Retry</VipButton>
      </p>
      <p v-else-if="!items.length">No operational notifications.</p>
      <ul class="ndrawer__list">
        <li v-for="n in items" :key="n.id" class="ndrawer__item" :class="{ 'is-unread': !n.read }" @click="open(n)">
          <VipBadge :tone="n.severity" variant="dot" size="sm" />
          <div class="ndrawer__body">
            <div class="ndrawer__title">
              {{ n.title }}<VipIcon name="chevronRight" :size="14" class="ndrawer__go" />
            </div>
            <div class="ndrawer__text">{{ n.body }}</div>
            <div class="ndrawer__time">{{ relativeTime(n.ts) }}</div>
          </div>
        </li>
      </ul>
    </template>
  </VipDrawer>
</template>

<style scoped>
.ndrawer__toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--vip-sp-5);
}
.ndrawer__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.ndrawer__item {
  display: flex;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-5);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  cursor: pointer;
}
.ndrawer__item:hover {
  background: var(--vip-surface-hover);
}
.ndrawer__item.is-unread {
  border-color: var(--vip-border);
  background: var(--vip-surface-2);
}
.ndrawer__body {
  flex: 1;
  min-width: 0;
}
.ndrawer__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ndrawer__go {
  color: var(--vip-text-disabled);
}
.ndrawer__text {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: 2px;
}
.ndrawer__time {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
  margin-top: var(--vip-sp-3);
}
</style>
