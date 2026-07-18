<script setup lang="ts">
import { ref, shallowRef, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { dashboardService, LAST_REFRESH } from './dashboards.service'
import { useDashboardEditor } from './useDashboardEditor'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import type { Dashboard } from '@/shared/types/dashboard'
import type { QueryFilter } from '@/shared/types/semantic'
import { relativeTime } from '@/shared/lib/format'
import DashboardGridCanvas from './DashboardGridCanvas.vue'
import DashboardFilterBar from './DashboardFilterBar.vue'
import DashboardShareDialog from './DashboardShareDialog.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()

const loading = ref(true)
// shallowRef so the composable's inner refs stay intact (reactive() unwraps them).
const editor = shallowRef<ReturnType<typeof useDashboardEditor>>()
const crossFilters = ref<QueryFilter[]>([])
const refreshedAt = ref(LAST_REFRESH)
const activePageId = computed<string>({
  get: () => editor.value?.activePageId.value ?? '',
  set: (v: string) => {
    if (editor.value) editor.value.activePageId.value = v
  },
})

async function load() {
  loading.value = true
  const d: Dashboard = await dashboardService.get(route.params.id as string)
  editor.value = useDashboardEditor(d)
  loading.value = false
}
function onCrossFilter({ field, value }: { field: string; value: string }) {
  const existing = crossFilters.value.find((f) => f.fieldId === field && f.value === value)
  if (existing) crossFilters.value = crossFilters.value.filter((f) => f !== existing)
  else
    crossFilters.value = [
      ...crossFilters.value.filter((f) => f.fieldId !== field),
      { fieldId: field, operator: 'eq', value, label: `${field} = ${value}` },
    ]
}
function refresh() {
  refreshedAt.value = new Date().toISOString()
  ui.pushToast({ kind: 'success', title: 'Data refreshed' })
}
const shareItems = [
  { key: 'link', label: 'Copy link', icon: 'link' },
  { key: 'export', label: 'Export (PDF/PNG/CSV)', icon: 'download' },
  { key: 'snapshot', label: 'Save snapshot', icon: 'image' },
  { key: 'email', label: 'Email delivery & schedule', icon: 'report' },
]
const shareOpen = ref(false)
const shareTab = ref<'export' | 'snapshot' | 'email'>('export')
function onShare(key: string) {
  if (key === 'link') {
    navigator.clipboard?.writeText(window.location.href)
    ui.pushToast({ kind: 'success', title: 'Link copied' })
    return
  }
  shareTab.value = key as 'export' | 'snapshot' | 'email'
  shareOpen.value = true
}
const fav = computed(() => editor.value?.dashboard.favorite ?? false)
function toggleFav() {
  if (editor.value) {
    editor.value.dashboard.favorite = !editor.value.dashboard.favorite
    dashboardService.toggleFavorite(editor.value.dashboard.id)
  }
}
onMounted(load)
</script>

<template>
  <div class="dview">
    <header class="dview__header">
      <div class="dview__head-left">
        <h1 class="dview__title">{{ editor?.dashboard.name }}</h1>
        <VipBadge :tone="editor?.dashboard.status === 'published' ? 'success' : 'neutral'" size="sm">{{
          editor?.dashboard.status
        }}</VipBadge>
        <span class="dview__fresh"><VipIcon name="clock" :size="13" /> Refreshed {{ relativeTime(refreshedAt) }}</span>
      </div>
      <div class="dview__head-right">
        <VipButton
          variant="ghost"
          size="sm"
          :icon="fav ? 'star' : 'star'"
          :class="{ 'is-fav': fav }"
          :title="fav ? 'Unfavorite' : 'Favorite'"
          @click="toggleFav"
        />
        <VipButton variant="ghost" size="sm" icon="refresh" title="Refresh" @click="refresh" />
        <VipButton
          v-if="platform.can('dashboard:write')"
          variant="secondary"
          size="sm"
          icon="settings"
          @click="router.push(`/dashboards/${editor?.dashboard.id}/edit`)"
          >Edit</VipButton
        >
        <VipMenu :items="shareItems" @select="onShare">
          <template #trigger><VipButton variant="primary" size="sm" icon="share">Share</VipButton></template>
        </VipMenu>
      </div>
    </header>

    <div v-if="loading" class="dview__loading"><VipSpinner :size="24" label="Loading dashboard…" /></div>
    <template v-else-if="editor">
      <div class="dview__pages" v-if="editor.dashboard.pages.length > 1">
        <button
          v-for="p in editor.dashboard.pages"
          :key="p.id"
          class="dview__page"
          :class="{ 'is-active': activePageId === p.id }"
          @click="activePageId = p.id"
        >
          {{ p.name }}
        </button>
      </div>
      <DashboardFilterBar
        :dashboard="editor.dashboard"
        :cross-filters="crossFilters"
        @clear-cross="crossFilters = []"
        @remove-cross="(f) => (crossFilters = crossFilters.filter((x) => x !== f))"
      />
      <div class="dview__canvas">
        <DashboardGridCanvas
          :editor="editor"
          :cross-filters="crossFilters"
          :editable="false"
          @cross-filter="onCrossFilter"
        />
      </div>
    </template>

    <DashboardShareDialog
      v-if="editor"
      :open="shareOpen"
      :dashboard="editor.dashboard"
      :initial-tab="shareTab"
      @close="shareOpen = false"
    />
  </div>
</template>

<style scoped>
.dview {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}
.dview__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-6) var(--vip-sp-8);
  border-bottom: 1px solid var(--vip-border-subtle);
  flex: none;
}
.dview__head-left {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.dview__title {
  font-size: var(--vip-fs-xl);
  font-weight: var(--vip-fw-semibold);
}
.dview__fresh {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.dview__head-right {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.dview__head-right :deep(.is-fav) {
  color: var(--vip-warning);
}
.dview__loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dview__pages {
  display: flex;
  gap: var(--vip-sp-2);
  padding: var(--vip-sp-3) var(--vip-sp-8) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.dview__page {
  padding: var(--vip-sp-4);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  margin-bottom: -1px;
}
.dview__page.is-active {
  color: var(--vip-text-primary);
  border-bottom-color: var(--vip-brand-500);
}
.dview__canvas {
  flex: 1;
  overflow: auto;
  padding: var(--vip-sp-8);
  background: var(--vip-bg-app);
}
</style>
