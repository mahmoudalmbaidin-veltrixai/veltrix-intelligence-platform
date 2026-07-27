<script setup lang="ts">
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { dashboardService, newDashboard } from './dashboards.service'
import { useDashboardEditor } from './useDashboardEditor'
import { useResizable } from '@/shared/composables/useResizable'
import { useIsCompact } from '@/shared/composables/useMediaQuery'
import { announce } from '@/shared/composables/useAnnouncer'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import type { Dashboard, WidgetType } from '@/shared/types/dashboard'
import { ApiError } from '@/shared/types/api'
import type { QueryFilter } from '@/shared/types/semantic'
import type { SemanticModel } from '@/shared/types/semantic'
import { semanticStudioService } from '@/modules/semantic/semantic.service'
import { relativeTime } from '@/shared/lib/format'
import FieldsPanel from './FieldsPanel.vue'
import DashboardGridCanvas from './DashboardGridCanvas.vue'
import WidgetInspector from './WidgetInspector.vue'
import DashboardFilterBar from './DashboardFilterBar.vue'
import DashboardShareDialog from './DashboardShareDialog.vue'
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
// shallowRef so the composable's inner refs stay intact (reactive() unwraps them).
const editor = shallowRef<ReturnType<typeof useDashboardEditor>>()
const modelId = ref('')
const models = ref<SemanticModel[]>([])
const mode = ref<'edit' | 'preview'>('edit')
const saving = ref(false)
const savedAt = ref<string | null>(null)
const crossFilters = ref<QueryFilter[]>([])
const dashboardFilters = ref<QueryFilter[]>([])
const fullscreen = ref(false)
const shareOpen = ref(false)
const conflict = ref(false)

const left = useResizable({ key: 'dash.left', initial: 256, min: 200, max: 380 })
const right = useResizable({ key: 'dash.right', initial: 320, min: 260, max: 460, invert: true })

// Compact (tablet/phone): fields + inspector become overlay panels.
const compact = useIsCompact()
const fieldsOpen = ref(false)
const inspectorOpen = ref(false)
function toggleFields() {
  fieldsOpen.value = !fieldsOpen.value
  inspectorOpen.value = false
}
function toggleInspector() {
  inspectorOpen.value = !inspectorOpen.value
  fieldsOpen.value = false
}
function closeOverlays() {
  fieldsOpen.value = false
  inspectorOpen.value = false
}
function addWidgetFromPanel(t: WidgetType) {
  const widget = editor.value?.addWidget(t)
  const model = models.value.find((item) => item.id === modelId.value) ?? models.value[0]
  if (widget && model && !['text', 'rich-text', 'image'].includes(t)) {
    const dimensions = model.fields.filter((field) => field.role === 'dimension' || field.role === 'time')
    const metrics = model.fields.filter((field) => field.role === 'metric')
    widget.modelId = model.id
    widget.wells = {}
    if (['kpi', 'metric-comparison', 'gauge', 'progress'].includes(t) && metrics[0]) {
      widget.wells.values = [{ fieldId: metrics[0].id, aggregation: 'sum' }]
    } else if (['bar', 'column', 'stacked-bar', 'line', 'area', 'pie', 'donut'].includes(t)) {
      if (dimensions[0]) widget.wells.category = [dimensions[0].id]
      if (metrics[0]) widget.wells.values = [{ fieldId: metrics[0].id, aggregation: 'sum' }]
    } else if (t === 'scatter') {
      if (dimensions[0]) widget.wells.category = [dimensions[0].id]
      widget.wells.values = metrics.slice(0, 2).map((field) => ({ fieldId: field.id, aggregation: 'sum' }))
    } else if (t === 'table' || t === 'pivot') {
      widget.wells.category = dimensions.slice(0, 3).map((field) => field.id)
      widget.wells.values = metrics.slice(0, 3).map((field) => ({ fieldId: field.id, aggregation: 'sum' }))
    } else if ((t === 'filter' || t === 'date-filter') && dimensions[0]) {
      widget.wells.category = [dimensions[0].id]
    }
  }
  if (compact.value) fieldsOpen.value = false
}

const canEdit = computed(() => platform.can('dashboard.create') || platform.can('dashboard.update'))

// Unwrapped accessors for template use (composable exposes refs).
const dirty = computed(() => editor.value?.dirty.value ?? false)
const canUndo = computed(() => editor.value?.canUndo.value ?? false)
const canRedo = computed(() => editor.value?.canRedo.value ?? false)
const activePageId = computed<string>({
  get: () => editor.value?.activePageId.value ?? '',
  set: (v: string) => {
    if (editor.value) editor.value.activePageId.value = v
  },
})

// Reveal the inspector when a widget is selected (compact) + announce it.
watch(
  () => editor.value?.selectedId.value ?? null,
  (id) => {
    if (!id) return
    if (compact.value) {
      inspectorOpen.value = true
      fieldsOpen.value = false
    }
    announce(`Selected ${editor.value?.selectedWidget.value?.general.name ?? 'widget'}`)
  },
)

async function load() {
  loading.value = true
  try {
    const id = route.params.id as string | undefined
    const [d, semanticModels] = await Promise.all([
      id ? dashboardService.get(id) : Promise.resolve(newDashboard()),
      semanticStudioService.listModels(),
    ])
    models.value = semanticModels
    modelId.value =
      d.pages.flatMap((page) => page.widgets).find((widget) => widget.modelId)?.modelId ?? semanticModels[0]?.id ?? ''
    editor.value = useDashboardEditor(d)
    dashboardFilters.value = [...d.filters]
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Dashboard could not load', message: ApiError.from(error).message })
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!editor.value || !canEdit.value) return
  const isFirstSave = route.name === 'dashboard-new' || route.path === '/dashboards/new'
  saving.value = true
  try {
    const saved = await dashboardService.save(editor.value.dashboard as Dashboard)
    editor.value = useDashboardEditor(saved)
    savedAt.value = saved.updatedAt
    conflict.value = false
    ui.pushToast({ kind: 'success', title: 'Dashboard saved' })
    // First save from /dashboards/new: adopt the stable ID URL so the dashboard
    // can be deep-linked and reloaded (QA VIP-FE-H004).
    if (isFirstSave) await router.replace(`/dashboards/${saved.id}/edit`)
  } catch (error) {
    const apiError = ApiError.from(error)
    if (apiError.code === 'DASHBOARD_VERSION_CONFLICT') {
      conflict.value = true
      window.clearTimeout(timer)
    } else {
      ui.pushToast({ kind: 'error', title: 'Dashboard was not saved', message: apiError.message })
    }
  } finally {
    saving.value = false
  }
}
async function publish() {
  if (!editor.value) return
  await save()
  if (conflict.value || !editor.value) return
  const p = await dashboardService.publish(editor.value.dashboard as Dashboard)
  editor.value.dashboard.status = p.status
  editor.value.dashboard.version = p.version
  ui.pushToast({ kind: 'success', title: 'Dashboard published', message: `Version ${p.version} is live` })
}
async function openGovernance() {
  if (editor.value?.dashboard.id !== 'new') shareOpen.value = true
}

async function reloadConflict() {
  conflict.value = false
  await load()
}
async function saveConflictCopy() {
  if (!editor.value) return
  editor.value.dashboard.id = 'new'
  editor.value.dashboard.version = 1
  editor.value.dashboard.name = `${editor.value.dashboard.name} copy`
  conflict.value = false
  await save()
}

function applyGovernanceUpdate(dashboard: Dashboard) {
  editor.value = useDashboardEditor(dashboard)
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
function updateDashboardFilters(filters: QueryFilter[]) {
  dashboardFilters.value = filters
  if (!editor.value) return
  editor.value.dashboard.filters = [...filters]
  editor.value.commit()
}

/* autosave */
let timer: number | undefined
watch(
  () => editor.value?.dirty.value,
  (d) => {
    // Creation is explicit. Autosaving a "new" dashboard can race the Save
    // action and issue two creates for the same slug.
    if (d && canEdit.value && editor.value?.dashboard.id !== 'new') {
      window.clearTimeout(timer)
      timer = window.setTimeout(async () => {
        if (!editor.value?.dirty.value) return
        try {
          const saved = await dashboardService.save(editor.value.dashboard as Dashboard)
          editor.value = useDashboardEditor(saved)
          savedAt.value = saved.updatedAt
        } catch (error) {
          if (ApiError.from(error).code === 'DASHBOARD_VERSION_CONFLICT') conflict.value = true
        }
      }, 2500)
    }
  },
)

function onKeydown(e: KeyboardEvent) {
  if (!editor.value) return
  const tag = (e.target as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
      e.preventDefault()
      save()
    }
    return
  }
  const mod = e.metaKey || e.ctrlKey
  const sel = editor.value.selectedId.value
  if (mod && e.key.toLowerCase() === 's') {
    e.preventDefault()
    save()
  } else if ((e.key === 'Delete' || e.key === 'Backspace') && sel) {
    e.preventDefault()
    editor.value.deleteWidget(sel)
  } else if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) {
    e.preventDefault()
    editor.value.undo()
  } else if (mod && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {
    e.preventDefault()
    editor.value.redo()
  } else if (mod && e.key.toLowerCase() === 'd' && sel) {
    e.preventDefault()
    editor.value.duplicateWidget(sel)
  } else if (mod && e.key.toLowerCase() === 'c' && sel) {
    editor.value.copyWidget(sel)
  } else if (mod && e.key.toLowerCase() === 'v') {
    editor.value.paste()
  } else if (e.key.startsWith('Arrow') && sel) {
    // Keyboard move (arrows) and resize (Shift+arrows) of the selected widget
    // on the 12-column grid (QA VIP-FE-C004).
    e.preventDefault()
    const w = editor.value.selectedWidget.value
    if (!w) return
    editor.value.beginChange()
    const dx = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0
    const dy = e.key === 'ArrowUp' ? -1 : e.key === 'ArrowDown' ? 1 : 0
    if (e.shiftKey) {
      editor.value.updatePosition(w.id, { ...w.pos, w: Math.max(2, w.pos.w + dx), h: Math.max(2, w.pos.h + dy) })
      announce(`Resized to ${Math.max(2, w.pos.w + dx)} by ${Math.max(2, w.pos.h + dy)}`)
    } else {
      editor.value.updatePosition(w.id, {
        ...w.pos,
        x: Math.max(0, Math.min(11, w.pos.x + dx)),
        y: Math.max(0, w.pos.y + dy),
      })
    }
  } else if (e.key === 'Escape') {
    fieldsOpen.value = false
    inspectorOpen.value = false
    editor.value.select(null)
  }
}

function beforeUnload(e: BeforeUnloadEvent) {
  if (editor.value?.dirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
onBeforeRouteLeave(() => (editor.value?.dirty.value ? window.confirm('You have unsaved changes. Leave anyway?') : true))

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
    <div v-if="conflict" class="dstudio__conflict" role="alertdialog" aria-labelledby="dashboard-conflict-title">
      <strong id="dashboard-conflict-title">This dashboard was updated by another user.</strong>
      <span>Your unsaved work has not overwritten the server version.</span>
      <VipButton size="sm" variant="primary" @click="reloadConflict">Reload latest</VipButton>
      <VipButton size="sm" variant="secondary" @click="saveConflictCopy">Save current work as copy</VipButton>
      <VipButton size="sm" variant="ghost" @click="conflict = false">Cancel</VipButton>
    </div>
    <header class="dstudio__toolbar">
      <div class="dstudio__tb-left">
        <VipButton variant="ghost" size="sm" icon="chevronLeft" title="Back" @click="router.push('/dashboards')" />
        <div class="dstudio__title">
          <input
            v-if="editor"
            v-model="editor.dashboard.name"
            class="dstudio__name"
            aria-label="Dashboard name"
            :readonly="!canEdit"
            @input="editor.commit()"
          />
          <div class="dstudio__meta">
            <VipBadge :tone="editor?.dashboard.status === 'published' ? 'success' : 'neutral'" size="sm">{{
              editor?.dashboard.status
            }}</VipBadge>
            <span class="dstudio__ver">v{{ editor?.dashboard.version }}</span>
            <span v-if="dirty" class="dstudio__dirty">● Unsaved</span>
            <span v-else-if="savedAt" class="dstudio__saved">Saved {{ relativeTime(savedAt) }}</span>
          </div>
        </div>
      </div>
      <div class="dstudio__tb-right">
        <div v-if="compact && mode === 'edit'" class="dstudio__group">
          <VipButton
            variant="ghost"
            size="sm"
            icon="panelRight"
            title="Fields & visuals"
            :active="fieldsOpen"
            :aria-expanded="fieldsOpen"
            aria-controls="dstudio-fields"
            @click="toggleFields"
          />
          <VipButton
            variant="ghost"
            size="sm"
            icon="settings"
            title="Inspector"
            :active="inspectorOpen"
            :aria-expanded="inspectorOpen"
            aria-controls="dstudio-inspector"
            @click="toggleInspector"
          />
        </div>
        <VipSegmented
          v-model="mode"
          :options="[
            { value: 'edit', label: 'Edit', icon: 'settings' },
            { value: 'preview', label: 'Preview', icon: 'eye' },
          ]"
          size="sm"
        />
        <div class="dstudio__group">
          <VipButton variant="ghost" size="sm" icon="undo" title="Undo" :disabled="!canUndo" @click="editor?.undo()" />
          <VipButton variant="ghost" size="sm" icon="redo" title="Redo" :disabled="!canRedo" @click="editor?.redo()" />
        </div>
        <VipButton variant="secondary" size="sm" icon="save" :loading="saving" :disabled="!canEdit" @click="save"
          >Save</VipButton
        >
        <VipButton
          variant="secondary"
          size="sm"
          icon="share"
          :disabled="!editor || editor.dashboard.id === 'new'"
          :title="
            !editor || editor.dashboard.id === 'new'
              ? 'Save the dashboard before managing governance'
              : 'Share, publish versions, snapshots, exports and delivery'
          "
          @click="openGovernance"
          >Share</VipButton
        >
        <VipButton variant="primary" size="sm" icon="upload" :disabled="!canEdit" @click="publish">Publish</VipButton>
        <VipButton
          variant="ghost"
          size="sm"
          :icon="fullscreen ? 'minimize' : 'maximize'"
          :title="fullscreen ? 'Exit fullscreen' : 'Enter fullscreen'"
          @click="fullscreen = !fullscreen"
        />
      </div>
    </header>

    <div v-if="loading" class="dstudio__loading"><VipSpinner :size="24" label="Loading dashboard…" /></div>

    <div v-else-if="editor" class="dstudio__body" :class="{ 'is-compact': compact }">
      <div v-if="compact && (fieldsOpen || inspectorOpen)" class="dstudio__scrim" @click="closeOverlays" />
      <div
        v-if="mode === 'edit'"
        id="dstudio-fields"
        class="dstudio__left"
        role="region"
        aria-label="Fields and visuals"
        :aria-hidden="compact && !fieldsOpen"
        :inert="compact && !fieldsOpen"
        :class="{ 'is-overlay': compact, 'is-open': fieldsOpen }"
        :style="compact ? {} : { width: `${left.size.value}px` }"
      >
        <FieldsPanel v-model:model-id="modelId" :models="models" @add-widget="addWidgetFromPanel" />
      </div>
      <div v-if="mode === 'edit' && !compact" class="dstudio__resizer" @pointerdown="left.startResize" />

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
            >
              {{ p.name }}
              <VipIcon
                v-if="mode === 'edit' && editor.dashboard.pages.length > 1"
                name="close"
                :size="11"
                class="dstudio__page-x"
                @click.stop="editor.removePage(p.id)"
              />
            </button>
            <button v-if="mode === 'edit'" class="dstudio__page-add" title="Add page" @click="editor.addPage()">
              <VipIcon name="plus" :size="14" />
            </button>
          </div>
        </div>

        <DashboardFilterBar
          :dashboard="editor.dashboard"
          :models="models"
          :model-id="modelId"
          :cross-filters="crossFilters"
          :filters="dashboardFilters"
          @update:filters="updateDashboardFilters"
          @clear-cross="crossFilters = []"
          @remove-cross="(f) => (crossFilters = crossFilters.filter((x) => x !== f))"
        />

        <div class="dstudio__canvas" @dragover.prevent @drop="onCanvasDrop">
          <DashboardGridCanvas
            :editor="editor"
            :cross-filters="[...dashboardFilters, ...crossFilters]"
            :editable="mode === 'edit' && canEdit"
            :draft-preview="true"
            @cross-filter="onCrossFilter"
          />
        </div>
      </div>

      <div v-if="mode === 'edit' && !compact" class="dstudio__resizer" @pointerdown="right.startResize" />
      <div
        v-if="mode === 'edit'"
        id="dstudio-inspector"
        class="dstudio__right"
        role="region"
        aria-label="Visual inspector"
        :aria-hidden="compact && !inspectorOpen"
        :inert="compact && !inspectorOpen"
        :class="{ 'is-overlay': compact, 'is-open': inspectorOpen }"
        :style="compact ? {} : { width: `${right.size.value}px` }"
      >
        <WidgetInspector :editor="editor" :models="models" />
      </div>
    </div>

    <DashboardShareDialog
      v-if="editor"
      :open="shareOpen"
      :dashboard="editor.dashboard"
      @close="shareOpen = false"
      @updated="applyGovernanceUpdate"
    />
  </div>
</template>

<style scoped>
.dstudio {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: var(--vip-bg-canvas);
}
.dstudio.is-fullscreen {
  position: fixed;
  inset: 0;
  z-index: var(--vip-z-modal);
}
.dstudio__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  height: 52px;
  padding: 0 var(--vip-sp-5);
  background: var(--vip-surface-1);
  border-bottom: 1px solid var(--vip-border);
  flex: none;
}
.dstudio__tb-left {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  min-width: 0;
}
.dstudio__name {
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-sm);
  padding: 2px 6px;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  max-width: 320px;
}
.dstudio__name:hover {
  border-color: var(--vip-border);
}
.dstudio__name:focus {
  border-color: var(--vip-brand-500);
  outline: none;
}
.dstudio__meta {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: 0 6px;
  margin-top: 2px;
}
.dstudio__ver {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.dstudio__dirty {
  font-size: var(--vip-fs-xs);
  color: var(--vip-warning-text);
}
.dstudio__saved {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
}
.dstudio__tb-right {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.dstudio__group {
  display: flex;
  gap: 2px;
}

.dstudio__loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dstudio__body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.dstudio__left,
.dstudio__right {
  flex: none;
  overflow: hidden;
  border-right: 1px solid var(--vip-border);
}
.dstudio__right {
  border-right: none;
  border-left: 1px solid var(--vip-border);
}
.dstudio__center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.dstudio__resizer {
  width: 5px;
  flex: none;
  cursor: col-resize;
  margin: 0 -2px;
  z-index: 2;
}
.dstudio__resizer:hover {
  background: var(--vip-brand-soft);
}

.dstudio__pages {
  border-bottom: 1px solid var(--vip-border-subtle);
  background: var(--vip-surface-1);
  padding: 0 var(--vip-sp-5);
  flex: none;
}
.dstudio__page-tabs {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
}
.dstudio__page-tab {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  padding: var(--vip-sp-4) var(--vip-sp-4);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  margin-bottom: -1px;
}
.dstudio__page-tab.is-active {
  color: var(--vip-text-primary);
  border-bottom-color: var(--vip-brand-500);
}
.dstudio__page-x {
  color: var(--vip-text-disabled);
  border-radius: 3px;
}
.dstudio__page-x:hover {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.dstudio__page-add {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--vip-text-muted);
  border-radius: var(--vip-radius-sm);
}
.dstudio__page-add:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}

.dstudio__canvas {
  flex: 1;
  overflow: auto;
  padding: var(--vip-sp-6);
}

/* ---- compact / responsive ---- */
.dstudio__scrim {
  position: absolute;
  inset: 0;
  background: var(--vip-scrim);
  z-index: 8;
}
.dstudio__body.is-compact {
  position: relative;
}
.dstudio__body.is-compact .dstudio__left,
.dstudio__body.is-compact .dstudio__right {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 9;
  width: min(88vw, 340px);
  box-shadow: var(--vip-shadow-lg);
  transition: transform var(--vip-motion-base) var(--vip-ease-emphasized);
}
.dstudio__body.is-compact .dstudio__left {
  left: 0;
  transform: translateX(-101%);
}
.dstudio__body.is-compact .dstudio__right {
  right: 0;
  transform: translateX(101%);
}
.dstudio__body.is-compact .dstudio__left.is-open {
  transform: translateX(0);
}
.dstudio__body.is-compact .dstudio__right.is-open {
  transform: translateX(0);
}

@media (max-width: 899px) {
  .dstudio__toolbar {
    flex-wrap: wrap;
    height: auto;
    min-height: 52px;
    padding: var(--vip-sp-3) var(--vip-sp-4);
    gap: var(--vip-sp-3);
  }
  .dstudio__tb-right {
    flex-wrap: wrap;
    gap: var(--vip-sp-2);
  }
  .dstudio__name {
    max-width: 40vw;
  }
  .dstudio__canvas {
    padding: var(--vip-sp-4);
  }
}
@media (max-width: 599px) {
  .dstudio__tb-left {
    min-width: 0;
    flex: 1;
  }
  .dstudio__meta {
    display: none;
  }
}
</style>
