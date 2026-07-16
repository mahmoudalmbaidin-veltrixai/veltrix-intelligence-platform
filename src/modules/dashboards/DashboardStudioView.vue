<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { dashboardService, newDashboard } from './dashboards.service'
import { useDashboardEditor } from './useDashboardEditor'
import { useResizable } from '@/shared/composables/useResizable'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import type { Dashboard, WidgetType } from '@/shared/types/dashboard'
import type { QueryFilter } from '@/shared/types/semantic'
import { relativeTime } from '@/shared/lib/format'
import FieldsPanel from './FieldsPanel.vue'
import DashboardGridCanvas from './DashboardGridCanvas.vue'
import WidgetInspector from './WidgetInspector.vue'
import DashboardFilterBar from './DashboardFilterBar.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()

const loading = ref(true)
const editor = ref<ReturnType<typeof useDashboardEditor>>()
const modelId = ref('sm_sales')
const mode = ref<'edit' | 'preview'>('edit')
const saving = ref(false)
const savedAt = ref<string | null>(null)
const crossFilters = ref<QueryFilter[]>([])
const fullscreen = ref(false)

const left = useResizable({ key: 'dash.left', initial: 256, min: 200, max: 380 })
const right = useResizable({ key: 'dash.right', initial: 320, min: 260, max: 460, invert: true })

const canEdit = computed(() => platform.can('dashboard:write'))

// Unwrapped accessors for template use (composable exposes refs).
const dirty = computed(() => editor.value?.dirty.value ?? false)
const canUndo = computed(() => editor.value?.canUndo.value ?? false)
const canRedo = computed(() => editor.value?.canRedo.value ?? false)
const activePageId = computed<string>({
  get: () => editor.value?.activePageId.value ?? '',
  set: (v: string) => { if (editor.value) editor.value.activePageId.value = v },
})

async function load() {
  loading.value = true
  const id = route.params.id as string | undefined
  const d: Dashboard = id ? await dashboardService.get(id) : newDashboard()
  editor.value = useDashboardEditor(d)
  loading.value = false
}

async function save() {
  if (!editor.value || !canEdit.value) return
  saving.value = true
  const saved = await dashboardService.save(editor.value.dashboard as Dashboard)
  editor.value.markSaved()
  savedAt.value = saved.updatedAt
  saving.value = false
  ui.pushToast({ kind: 'success', title: 'Dashboard saved' })
}
async function publish() {
  if (!editor.value) return
  await save()
  const p = await dashboardService.publish(editor.value.dashboard as Dashboard)
  editor.value.dashboard.status = p.status
  editor.value.dashboard.version = p.version
  ui.pushToast({ kind: 'success', title: 'Dashboard published', message: `Version ${p.version} is live` })
}

function onCrossFilter({ field, value }: { field: string; value: string }) {
  const existing = crossFilters.value.find((f) => f.fieldId === field && f.value === value)
  if (existing) crossFilters.value = crossFilters.value.filter((f) => f !== existing)
  else crossFilters.value = [...crossFilters.value.filter((f) => f.fieldId !== field), { fieldId: field, operator: 'eq', value, label: `${field} = ${value}` }]
}

/* autosave */
let timer: number | undefined
watch(() => editor.value?.dirty, (d) => {
  if (d && canEdit.value) {
    window.clearTimeout(timer)
    timer = window.setTimeout(async () => {
      if (!editor.value?.dirty) return
      await dashboardService.save(editor.value.dashboard as Dashboard)
      editor.value.markSaved()
      savedAt.value = new Date().toISOString()
    }, 2500)
  }
})

function onKeydown(e: KeyboardEvent) {
  if (!editor.value) return
  const tag = (e.target as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save() }
    return
  }
  const mod = e.metaKey || e.ctrlKey
  const sel = editor.value.selectedId.value
  if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); save() }
  else if ((e.key === 'Delete' || e.key === 'Backspace') && sel) { e.preventDefault(); editor.value.deleteWidget(sel) }
  else if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); editor.value.undo() }
  else if (mod && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) { e.preventDefault(); editor.value.redo() }
  else if (mod && e.key.toLowerCase() === 'd' && sel) { e.preventDefault(); editor.value.duplicateWidget(sel) }
  else if (mod && e.key.toLowerCase() === 'c' && sel) { editor.value.copyWidget(sel) }
  else if (mod && e.key.toLowerCase() === 'v') { editor.value.paste() }
  else if (e.key === 'Escape') { editor.value.select(null) }
}

function beforeUnload(e: BeforeUnloadEvent) { if (editor.value?.dirty) { e.preventDefault(); e.returnValue = '' } }
onBeforeRouteLeave(() => (editor.value?.dirty ? window.confirm('You have unsaved changes. Leave anyway?') : true))

function renamePagePrompt(id: string, current: string) {
  if (mode.value !== 'edit' || !editor.value) return
  const name = window.prompt('Page name', current)
  if (name) editor.value.renamePage(id, name)
}

/* drop widget from fields panel onto canvas area */
function onCanvasDrop(e: DragEvent) {
  const t = e.dataTransfer?.getData('application/vip-widget') as WidgetType
  if (t && editor.value) editor.value.addWidget(t)
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('beforeunload', beforeUnload)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('beforeunload', beforeUnload)
})
</script>

<template>
  <div class="dstudio" :class="{ 'is-fullscreen': fullscreen }">
    <header class="dstudio__toolbar">
      <div class="dstudio__tb-left">
        <VipButton variant="ghost" size="sm" icon="chevronLeft" title="Back" @click="router.push('/dashboards')" />
        <div class="dstudio__title">
          <input v-if="editor" v-model="editor.dashboard.name" class="dstudio__name" aria-label="Dashboard name" :readonly="!canEdit" @input="editor.commit()" />
          <div class="dstudio__meta">
            <VipBadge :tone="editor?.dashboard.status === 'published' ? 'success' : 'neutral'" size="sm">{{ editor?.dashboard.status }}</VipBadge>
            <span class="dstudio__ver">v{{ editor?.dashboard.version }}</span>
            <span v-if="dirty" class="dstudio__dirty">● Unsaved</span>
            <span v-else-if="savedAt" class="dstudio__saved">Saved {{ relativeTime(savedAt) }}</span>
          </div>
        </div>
      </div>
      <div class="dstudio__tb-right">
        <VipSegmented v-model="mode" :options="[{ value: 'edit', label: 'Edit', icon: 'settings' }, { value: 'preview', label: 'Preview', icon: 'eye' }]" size="sm" />
        <div class="dstudio__group">
          <VipButton variant="ghost" size="sm" icon="undo" title="Undo" :disabled="!canUndo" @click="editor?.undo()" />
          <VipButton variant="ghost" size="sm" icon="redo" title="Redo" :disabled="!canRedo" @click="editor?.redo()" />
        </div>
        <VipButton variant="secondary" size="sm" icon="save" :loading="saving" :disabled="!canEdit" @click="save">Save</VipButton>
        <VipButton variant="primary" size="sm" icon="upload" :disabled="!canEdit" @click="publish">Publish</VipButton>
        <VipButton variant="ghost" size="sm" :icon="fullscreen ? 'minimize' : 'maximize'" @click="fullscreen = !fullscreen" />
      </div>
    </header>

    <div v-if="loading" class="dstudio__loading"><VipSpinner :size="24" label="Loading dashboard…" /></div>

    <div v-else-if="editor" class="dstudio__body">
      <div v-if="mode === 'edit'" class="dstudio__left" :style="{ width: `${left.size.value}px` }">
        <FieldsPanel v-model:model-id="modelId" @add-widget="editor.addWidget($event)" />
      </div>
      <div v-if="mode === 'edit'" class="dstudio__resizer" @pointerdown="left.startResize" />

      <div class="dstudio__center">
        <!-- page tabs + filter bar -->
        <div class="dstudio__pages">
          <div class="dstudio__page-tabs">
            <button
              v-for="p in editor.dashboard.pages"
              :key="p.id"
              class="dstudio__page-tab"
              :class="{ 'is-active': activePageId === p.id }"
              @click="activePageId = p.id"
              @dblclick="renamePagePrompt(p.id, p.name)"
            >{{ p.name }}
              <VipIcon v-if="mode === 'edit' && editor.dashboard.pages.length > 1" name="close" :size="11" class="dstudio__page-x" @click.stop="editor.removePage(p.id)" />
            </button>
            <button v-if="mode === 'edit'" class="dstudio__page-add" title="Add page" @click="editor.addPage()"><VipIcon name="plus" :size="14" /></button>
          </div>
        </div>

        <DashboardFilterBar :dashboard="editor.dashboard" :cross-filters="crossFilters" @clear-cross="crossFilters = []" @remove-cross="(f) => crossFilters = crossFilters.filter((x) => x !== f)" />

        <div class="dstudio__canvas" @dragover.prevent @drop="onCanvasDrop">
          <DashboardGridCanvas
            :editor="editor"
            :cross-filters="crossFilters"
            :editable="mode === 'edit' && canEdit"
            @cross-filter="onCrossFilter"
          />
        </div>
      </div>

      <div v-if="mode === 'edit'" class="dstudio__resizer" @pointerdown="right.startResize" />
      <div v-if="mode === 'edit'" class="dstudio__right" :style="{ width: `${right.size.value}px` }">
        <WidgetInspector :editor="editor" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.dstudio { display: flex; flex-direction: column; height: 100vh; width: 100%; background: var(--vip-bg-canvas); }
.dstudio.is-fullscreen { position: fixed; inset: 0; z-index: var(--vip-z-modal); }
.dstudio__toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-5); height: 52px; padding: 0 var(--vip-sp-5); background: var(--vip-surface-1); border-bottom: 1px solid var(--vip-border); flex: none; }
.dstudio__tb-left { display: flex; align-items: center; gap: var(--vip-sp-4); min-width: 0; }
.dstudio__name { background: none; border: 1px solid transparent; border-radius: var(--vip-radius-sm); padding: 2px 6px; color: var(--vip-text-primary); font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); max-width: 320px; }
.dstudio__name:hover { border-color: var(--vip-border); }
.dstudio__name:focus { border-color: var(--vip-brand-500); outline: none; }
.dstudio__meta { display: flex; align-items: center; gap: var(--vip-sp-4); padding: 0 6px; margin-top: 2px; }
.dstudio__ver { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.dstudio__dirty { font-size: var(--vip-fs-xs); color: var(--vip-warning-text); }
.dstudio__saved { font-size: var(--vip-fs-xs); color: var(--vip-text-disabled); }
.dstudio__tb-right { display: flex; align-items: center; gap: var(--vip-sp-4); }
.dstudio__group { display: flex; gap: 2px; }

.dstudio__loading { flex: 1; display: flex; align-items: center; justify-content: center; }
.dstudio__body { flex: 1; display: flex; min-height: 0; }
.dstudio__left, .dstudio__right { flex: none; overflow: hidden; border-right: 1px solid var(--vip-border); }
.dstudio__right { border-right: none; border-left: 1px solid var(--vip-border); }
.dstudio__center { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.dstudio__resizer { width: 5px; flex: none; cursor: col-resize; margin: 0 -2px; z-index: 2; }
.dstudio__resizer:hover { background: var(--vip-brand-soft); }

.dstudio__pages { border-bottom: 1px solid var(--vip-border-subtle); background: var(--vip-surface-1); padding: 0 var(--vip-sp-5); flex: none; }
.dstudio__page-tabs { display: flex; align-items: center; gap: var(--vip-sp-2); }
.dstudio__page-tab { display: inline-flex; align-items: center; gap: var(--vip-sp-2); padding: var(--vip-sp-4) var(--vip-sp-4); background: none; border: none; border-bottom: 2px solid transparent; color: var(--vip-text-muted); font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-medium); margin-bottom: -1px; }
.dstudio__page-tab.is-active { color: var(--vip-text-primary); border-bottom-color: var(--vip-brand-500); }
.dstudio__page-x { color: var(--vip-text-disabled); border-radius: 3px; }
.dstudio__page-x:hover { background: var(--vip-danger-soft); color: var(--vip-danger-text); }
.dstudio__page-add { width: 26px; height: 26px; display: inline-flex; align-items: center; justify-content: center; background: none; border: none; color: var(--vip-text-muted); border-radius: var(--vip-radius-sm); }
.dstudio__page-add:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }

.dstudio__canvas { flex: 1; overflow: auto; padding: var(--vip-sp-6); }
</style>
