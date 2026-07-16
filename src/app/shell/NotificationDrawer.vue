<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import { isoAgo as agoIso } from '@/shared/lib/mock'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const ui = useUiStore()
const router = useRouter()

interface Notif { id: string; severity: 'info' | 'success' | 'warning' | 'danger'; title: string; body: string; ts: string; to: string; read: boolean }
const items = ref<Notif[]>([
  { id: 'n1', severity: 'danger', title: 'Pipeline failed', body: 'Revenue Nightly ETL failed at node "Join Orders".', ts: agoIso(18), to: '/pipelines/pl_revenue/runs', read: false },
  { id: 'n2', severity: 'success', title: 'Dataset refreshed', body: 'fct_orders refreshed — 2.4M rows, quality 98%.', ts: agoIso(52), to: '/datasets/ds_orders', read: false },
  { id: 'n3', severity: 'warning', title: 'Quota approaching', body: 'AI agent runs at 82% of monthly entitlement.', ts: agoIso(140), to: '/usage', read: false },
  { id: 'n4', severity: 'info', title: 'Approval requested', body: 'Q3 Board Report awaiting your approval.', ts: agoIso(220), to: '/automation/approvals', read: false },
  { id: 'n5', severity: 'info', title: 'Dashboard shared', body: 'A. Rahman shared "Executive Overview" with Analytics.', ts: agoIso(600), to: '/dashboards', read: true },
])

function markAll() {
  items.value = items.value.map((n) => ({ ...n, read: true }))
  ui.unreadNotifications = 0
}
function open(n: Notif) {
  n.read = true
  ui.unreadNotifications = items.value.filter((x) => !x.read).length
  ui.notificationDrawerOpen = false
  router.push(n.to)
}
</script>

<template>
  <VipDrawer :open="ui.notificationDrawerOpen" title="Notifications" :width="420" @close="ui.notificationDrawerOpen = false">
    <template #default>
      <div class="ndrawer__toolbar">
        <VipButton variant="ghost" size="sm" icon="check" @click="markAll">Mark all read</VipButton>
        <VipButton variant="ghost" size="sm" icon="external" @click="ui.notificationDrawerOpen = false; router.push('/notifications')">Open center</VipButton>
      </div>
      <ul class="ndrawer__list">
        <li v-for="n in items" :key="n.id" class="ndrawer__item" :class="{ 'is-unread': !n.read }" @click="open(n)">
          <VipBadge :tone="n.severity" variant="dot" size="sm" />
          <div class="ndrawer__body">
            <div class="ndrawer__title">{{ n.title }}<VipIcon name="chevronRight" :size="14" class="ndrawer__go" /></div>
            <div class="ndrawer__text">{{ n.body }}</div>
            <div class="ndrawer__time">{{ relativeTime(n.ts) }}</div>
          </div>
        </li>
      </ul>
    </template>
  </VipDrawer>
</template>

<style scoped>
.ndrawer__toolbar { display: flex; justify-content: space-between; margin-bottom: var(--vip-sp-5); }
.ndrawer__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.ndrawer__item {
  display: flex; gap: var(--vip-sp-4); padding: var(--vip-sp-5);
  border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); cursor: pointer;
}
.ndrawer__item:hover { background: var(--vip-surface-hover); }
.ndrawer__item.is-unread { border-color: var(--vip-border); background: var(--vip-surface-2); }
.ndrawer__body { flex: 1; min-width: 0; }
.ndrawer__title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); display: flex; align-items: center; justify-content: space-between; }
.ndrawer__go { color: var(--vip-text-disabled); }
.ndrawer__text { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); margin-top: 2px; }
.ndrawer__time { font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); margin-top: var(--vip-sp-3); }
</style>
