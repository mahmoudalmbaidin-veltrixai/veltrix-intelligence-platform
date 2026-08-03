<script setup lang="ts">
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { pipelineService, newDraft } from './pipelines.service'
import { usePipelineEditor } from './usePipelineEditor'
import { usePipelineRunner } from './usePipelineRunner'
import { usePipelinePermissions } from './usePipelinePermissions'
import { useResizable } from '@/shared/composables/useResizable'
import { useIsCompact } from '@/shared/composables/useMediaQuery'
import { announce } from '@/shared/composables/useAnnouncer'
import { useUiStore } from '@/shared/stores/ui'
import type {
  NodeExecStatus,
  Pipeline,
  PipelineArtifact,
  PipelineNodeKind,
  ValidationReport,
} from '@/shared/types/pipeline'
import { ApiError } from '@/shared/types/api'
import { relativeTime, formatDuration } from '@/shared/lib/format'
import NodePalette from './NodePalette.vue'
import PipelineCanvas from './PipelineCanvas.vue'
import NodeInspector from './NodeInspector.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import ResourceShareButton from '@/modules/access/ResourceShareButton.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()

const loading = ref(true)
// shallowRef (not ref) so the composable's inner refs are NOT unwrapped by
// reactive() — the studio + canvas access them as refs (`.value`).
const editor = shallowRef<ReturnType<typeof usePipelineEditor>>()
const runner = usePipelineRunner()
const canvasRef = ref<InstanceType<typeof PipelineCanvas>>()

const validation = ref<ValidationReport | null>(null)
const bottomTab = ref<'validation' | 'logs' | 'results'>('validation')
const saving = ref(false)
const autosaveAt = ref<string | null>(null)

const leftPanel = useResizable({ key: 'pipeline.left', initial: 260, min: 200, max: 400 })
const rightPanel = useResizable({ key: 'pipeline.right', initial: 330, min: 260, max: 520, invert: true })
const bottomPanel = useResizable({ key: 'pipeline.bottom', initial: 200, min: 120, max: 420, axis: 'y', invert: true })
const bottomOpen = ref(true)
function setBottomTab(v: 'validation' | 'logs' | 'results') {
  bottomTab.value = v
  bottomOpen.value = true
}
const fullscreen = ref(false)

// Compact (tablet/phone) mode: palette + inspector become overlay panels.
const compact = useIsCompact()
const paletteOpen = ref(false)
const inspectorOpen = ref(false)
function togglePalette() {
  paletteOpen.value = !paletteOpen.value
  inspectorOpen.value = false
}
function toggleInspector() {
  inspectorOpen.value = !inspectorOpen.value
  paletteOpen.value = false
}
function closeOverlays() {
  paletteOpen.value = false
  inspectorOpen.value = false
}
function addPaletteNode(kind: PipelineNodeKind) {
  if (!canEdit.value) return
  editor.value?.addNode(kind, 200, 160)
  if (compact.value) paletteOpen.value = false
}

// Resource-aware permission states from the backend's effective-access decision
// (echoed on the pipeline read). This is a UX convenience — the API enforces
// every action independently — but it keeps the toolbar honest per persona.
const pipelineRef = computed(() => editor.value?.pipeline as Pipeline | undefined)
const perms = usePipelinePermissions(pipelineRef)
const canEdit = computed(() => perms.canEdit.value)
const canRun = computed(() => perms.canRun.value)
const canManage = computed(() => perms.canManage.value)
const accessLevel = computed(() => perms.level.value)

// Unwrapped accessors for template use (composable exposes refs).
const dirty = computed(() => editor.value?.dirty.value ?? false)
// Publishing is available whenever there are unpublished changes: a never- or
// re-drafted pipeline (status !== 'published') or unsaved edits on top of a
// published version. A clean, already-published pipeline has nothing to publish.
const canPublish = computed(() => canEdit.value && (editor.value?.pipeline.status !== 'published' || dirty.value))
const canUndo = computed(() => canEdit.value && (editor.value?.canUndo.value ?? false))
const canRedo = computed(() => canEdit.value && (editor.value?.canRedo.value ?? false))

/* ---- run artifacts (Results tab) ---- */
const artifacts = ref<PipelineArtifact[]>([])
const artifactsLoading = ref(false)
const artifactsError = ref<string | null>(null)
const downloadingArtifactId = ref<string | null>(null)

async function loadArtifacts() {
  const run = runner.run.value
  const pipelineId = editor.value?.pipeline.id
  artifacts.value = []
  artifactsError.value = null
  if (!run || !pipelineId || pipelineId === 'new') return
  artifactsLoading.value = true
  try {
    artifacts.value = await pipelineService.listArtifacts(pipelineId, run.id)
  } catch (error) {
    artifactsError.value = error instanceof ApiError ? error.message : 'Unable to load artifacts for this run.'
  } finally {
    artifactsLoading.value = false
  }
}

async function downloadArtifact(artifact: PipelineArtifact) {
  const pipelineId = editor.value?.pipeline.id
  const run = runner.run.value
  if (!pipelineId || !run) return
  downloadingArtifactId.value = artifact.id
  try {
    const link = await pipelineService.createArtifactDownloadUrl(pipelineId, run.id, artifact.id)
    window.open(link.url, '_blank', 'noopener')
  } catch (error) {
    ui.pushToast({
      kind: 'error',
      title: 'Download failed',
      message: error instanceof ApiError ? error.message : 'The artifact could not be downloaded (expired or missing).',
    })
  } finally {
    downloadingArtifactId.value = null
  }
}

watch(
  () => runner.run.value?.id,
  () => {
    void loadArtifacts()
  },
)

// Reveal the inspector when a single node is selected (compact) and announce
// the selection to screen readers.
watch(
  () => (editor.value ? editor.value.selection.value.size : 0),
  (size) => {
    if (size === 1 && editor.value) {
      if (compact.value) {
        inspectorOpen.value = true
        paletteOpen.value = false
      }
      announce(`Selected node ${editor.value.selectedNode.value?.title ?? ''}`)
    } else if (size > 1) {
      announce(`${size} nodes selected`)
    }
  },
)

async function load() {
  loading.value = true
  const id = route.params.id as string | undefined
  try {
    const pipeline: Pipeline = id && id !== 'new' ? await pipelineService.get(id) : newDraft()
    editor.value = usePipelineEditor(pipeline)
    validation.value = editor.value.validate()
  } catch (error) {
    // The backend is the authority on per-resource access: an explicit deny or a
    // pipeline the user cannot see surfaces as forbidden/not-found. Route to the
    // standard forbidden page instead of leaving a broken studio.
    const kind = error instanceof ApiError ? error.kind : undefined
    if (kind === 'forbidden' || kind === 'not-found') {
      await router.replace({ name: 'forbidden', query: { from: route.fullPath } })
      return
    }
    throw error
  } finally {
    loading.value = false
  }
}

/* ---- execution status map for canvas ---- */
const execStatuses = computed(() => {
  const map = new Map<string, NodeExecStatus>()
  runner.run.value?.nodeStates.forEach((s) => map.set(s.nodeId, s.status))
  return map
})

watch(
  () => runner.run.value?.status,
  (s) => {
    if (s === 'succeeded')
      ui.pushToast({
        kind: 'success',
        title: 'Run succeeded',
        message: `${runner.run.value?.rowsProcessed.toLocaleString()} rows processed`,
      })
    else if (s === 'failed')
      ui.pushToast({
        kind: 'error',
        title: 'Run failed',
        message: `Correlation ID: ${runner.run.value?.correlationId}`,
      })
  },
)

/* ---- actions ---- */
async function persist(showToast = false) {
  if (!editor.value || !canEdit.value) return
  const isFirstSave = editor.value.pipeline.id === 'new'
  saving.value = true
  try {
    const saved = isFirstSave
      ? await pipelineService.create(editor.value.pipeline as Pipeline)
      : await pipelineService.save(editor.value.pipeline as Pipeline)
    Object.assign(editor.value.pipeline, saved)
    editor.value.markSaved()
    autosaveAt.value = saved.updatedAt
    if (isFirstSave) await router.replace(`/pipelines/${saved.id}`)
    if (showToast) ui.pushToast({ kind: 'success', title: 'Pipeline saved' })
    return saved
  } finally {
    saving.value = false
  }
}

async function save() {
  await persist(true)
}

async function runValidation() {
  if (!editor.value || !canEdit.value) return
  await persist()
  validation.value = await pipelineService.validate(editor.value.pipeline.id)
  bottomTab.value = 'validation'
  bottomOpen.value = true
  if (validation.value.valid)
    ui.pushToast({
      kind: 'success',
      title: 'Validation passed',
      message: `${validation.value.issues.length} advisory notes`,
    })
  else
    ui.pushToast({
      kind: 'warning',
      title: 'Validation found issues',
      message: `${validation.value.issues.filter((i) => i.level === 'error').length} errors`,
    })
}

async function publish() {
  if (!editor.value || !canEdit.value) return
  await persist()
  const report = await pipelineService.validate(editor.value.pipeline.id)
  validation.value = report
  if (!report.valid) {
    bottomTab.value = 'validation'
    bottomOpen.value = true
    ui.pushToast({ kind: 'error', title: 'Cannot publish', message: 'Resolve validation errors first.' })
    return
  }
  const published = await pipelineService.publish(editor.value.pipeline as Pipeline)
  Object.assign(editor.value.pipeline, await pipelineService.get(editor.value.pipeline.id))
  ui.pushToast({ kind: 'success', title: 'Pipeline published', message: `Version ${published.version} is now live` })
}

async function run() {
  if (!editor.value || !canRun.value) return
  await persist()
  const report = await pipelineService.validate(editor.value.pipeline.id)
  if (!report.valid) {
    validation.value = report
    bottomTab.value = 'validation'
    bottomOpen.value = true
    ui.pushToast({ kind: 'warning', title: 'Fix errors before running' })
    return
  }
  bottomTab.value = 'logs'
  bottomOpen.value = true
  await runner.start(editor.value.pipeline.id)
}

async function retry() {
  if (!runner.run.value || !canRun.value) return
  await runner.retry()
}

const runMenuItems = [
  { key: 'schedule', label: 'Configure schedule…', icon: 'calendar' },
  { key: 'deps', label: 'View dependencies', icon: 'lineage' },
  { key: 'versions', label: 'Version history', icon: 'clock' },
].filter((item) => item.key !== 'schedule')
async function onRunMenu(key: string) {
  if (key === 'versions' && editor.value) {
    const versions = await pipelineService.versions(editor.value.pipeline.id)
    ui.pushToast({
      kind: 'info',
      title: 'Version history',
      message: versions.length
        ? `${versions.length} immutable version${versions.length === 1 ? '' : 's'}; latest is v${versions[0].version_number}.`
        : 'This pipeline has not been published yet.',
    })
  } else if (key === 'schedule')
    ui.pushToast({
      kind: 'info',
      title: 'Schedule',
      message: 'Schedule editor — cron & triggers (backend dependency).',
    })
  else
    ui.pushToast({
      kind: 'info',
      title: 'Dependencies',
      message: 'Upstream/downstream lineage available in Data Lineage.',
    })
}

/* ---- keyboard shortcuts ---- */
function onKeydown(e: KeyboardEvent) {
  if (!editor.value) return
  const tag = (e.target as HTMLElement).tagName
  const typing = tag === 'INPUT' || tag === 'TEXTAREA'
  const mod = e.metaKey || e.ctrlKey
  if (mod && e.key.toLowerCase() === 's') {
    e.preventDefault()
    if (canEdit.value) save()
    return
  }
  if (typing) return
  // Escape / select-all remain available in read-only; mutations require canEdit.
  if (e.key === 'Escape') {
    canvasRef.value?.cancelKeyboardConnect()
    paletteOpen.value = false
    inspectorOpen.value = false
    editor.value.clearSelection()
    return
  }
  if (mod && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    editor.value.selectMany(editor.value.pipeline.nodes.map((n) => n.id))
    return
  }
  if (!canEdit.value) return
  const edge = editor.value.selectedEdge.value
  if ((e.key === 'Delete' || e.key === 'Backspace') && editor.value.selection.value.size) {
    e.preventDefault()
    editor.value.deleteNodes([...editor.value.selection.value])
  } else if (e.key === 'Delete' && edge) {
    editor.value.deleteEdge(edge)
  } else if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) {
    e.preventDefault()
    editor.value.undo()
  } else if (mod && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {
    e.preventDefault()
    editor.value.redo()
  } else if (mod && e.key.toLowerCase() === 'c') {
    editor.value.copySelection()
  } else if (mod && e.key.toLowerCase() === 'v') {
    editor.value.paste()
  } else if (mod && e.key.toLowerCase() === 'd') {
    e.preventDefault()
    editor.value.duplicateNodes([...editor.value.selection.value])
  } else if (e.key.startsWith('Arrow') && editor.value.selection.value.size) {
    // Keyboard move of the selected node(s) (QA VIP-FE-C003).
    e.preventDefault()
    const step = e.shiftKey ? 1 : 16
    const dx = e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0
    const dy = e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0
    editor.value.moveNodes([...editor.value.selection.value], dx, dy)
    editor.value.commit()
  }
}

/* ---- autosave (debounced on dirty) ---- */
let autosaveTimer: number | undefined
watch(
  () => editor.value?.dirty.value,
  (d) => {
    // A new pipeline is created only by an explicit Save. Otherwise a long
    // source upload can race an autosave that replaces the editor instance,
    // leaving the completed source binding on a detached draft.
    if (d && canEdit.value && editor.value?.pipeline.id !== 'new') {
      window.clearTimeout(autosaveTimer)
      autosaveTimer = window.setTimeout(async () => {
        if (!editor.value?.dirty.value) return
        await persist()
      }, 2500)
    }
  },
)

/* ---- unsaved protection ---- */
function beforeUnload(e: BeforeUnloadEvent) {
  if (editor.value?.dirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
onBeforeRouteLeave(() => {
  if (editor.value?.dirty.value) {
    return window.confirm('You have unsaved changes. Leave anyway?')
  }
  return true
})

const errorCount = computed(() => validation.value?.issues.filter((i) => i.level === 'error').length ?? 0)
const warnCount = computed(() => validation.value?.issues.filter((i) => i.level === 'warning').length ?? 0)

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
  <div class="pstudio" :class="{ 'is-fullscreen': fullscreen }">
    <!-- toolbar -->
    <header class="pstudio__toolbar">
      <div class="pstudio__tb-left">
        <VipButton
          variant="ghost"
          size="sm"
          icon="chevronLeft"
          title="Back to pipelines"
          @click="router.push('/pipelines')"
        />
        <div class="pstudio__title">
          <input
            v-if="editor"
            v-model="editor.pipeline.name"
            class="pstudio__name"
            aria-label="Pipeline name"
            :readonly="!canEdit"
            @input="editor.commit()"
          />
          <div class="pstudio__meta">
            <VipBadge :tone="editor?.pipeline.status === 'published' ? 'success' : 'neutral'" size="sm">{{
              editor?.pipeline.status
            }}</VipBadge>
            <VipBadge
              v-if="accessLevel && accessLevel !== 'owner'"
              tone="info"
              size="sm"
              :title="`Your access to this pipeline: ${accessLevel}`"
              data-testid="pstudio-access-badge"
              >{{ accessLevel }}</VipBadge
            >
            <span v-if="!canEdit" class="pstudio__readonly" data-testid="pstudio-readonly">Read-only</span>
            <span class="pstudio__ver">v{{ editor?.pipeline.version }}</span>
            <span v-if="dirty" class="pstudio__dirty">● Unsaved</span>
            <span v-else-if="autosaveAt" class="pstudio__saved">Saved {{ relativeTime(autosaveAt) }}</span>
          </div>
        </div>
      </div>

      <div class="pstudio__tb-right">
        <div v-if="compact" class="pstudio__group">
          <VipButton
            variant="ghost"
            size="sm"
            icon="panelRight"
            title="Node palette"
            :active="paletteOpen"
            :aria-expanded="paletteOpen"
            aria-controls="pstudio-palette"
            @click="togglePalette"
          />
          <VipButton
            variant="ghost"
            size="sm"
            icon="settings"
            title="Inspector"
            :active="inspectorOpen"
            :aria-expanded="inspectorOpen"
            aria-controls="pstudio-inspector"
            @click="toggleInspector"
          />
        </div>
        <div class="pstudio__group">
          <VipButton
            variant="ghost"
            size="sm"
            icon="undo"
            title="Undo (⌘Z)"
            :disabled="!canUndo"
            @click="editor?.undo()"
          />
          <VipButton
            variant="ghost"
            size="sm"
            icon="redo"
            title="Redo (⌘⇧Z)"
            :disabled="!canRedo"
            @click="editor?.redo()"
          />
        </div>
        <div class="pstudio__group">
          <VipButton
            variant="secondary"
            size="sm"
            icon="check"
            :disabled="!canEdit"
            title="Validate the pipeline (requires edit access)"
            @click="runValidation"
            >Validate</VipButton
          >
          <VipButton variant="secondary" size="sm" icon="save" :loading="saving" :disabled="!canEdit" @click="save"
            >Save</VipButton
          >
        </div>
        <VipButton
          v-if="!runner.isRunning.value"
          variant="primary"
          size="sm"
          icon="play"
          :disabled="!canRun"
          title="Run the pipeline (requires operator access)"
          @click="run"
          >Run</VipButton
        >
        <VipButton v-else variant="danger" size="sm" icon="close" :disabled="!canRun" @click="runner.cancel()"
          >Cancel</VipButton
        >
        <VipButton variant="secondary" size="sm" icon="upload" :disabled="!canPublish" @click="publish"
          >Publish</VipButton
        >
        <ResourceShareButton
          v-if="canManage && editor?.pipeline.id && editor.pipeline.id !== 'new'"
          resource-type="pipeline"
          :resource-id="editor.pipeline.id"
          :resource-name="editor.pipeline.name"
          variant="secondary"
          size="sm"
        />
        <VipMenu :items="runMenuItems" @select="onRunMenu">
          <template #trigger><VipButton variant="ghost" size="sm" icon="dotsV" title="More" /></template>
        </VipMenu>
        <VipButton
          variant="ghost"
          size="sm"
          :icon="fullscreen ? 'minimize' : 'maximize'"
          :title="fullscreen ? 'Exit fullscreen' : 'Fullscreen'"
          @click="fullscreen = !fullscreen"
        />
      </div>
    </header>

    <div v-if="loading" class="pstudio__loading"><VipSpinner :size="24" label="Loading pipeline…" /></div>

    <div v-else-if="editor" class="pstudio__body">
      <div class="pstudio__main" :class="{ 'is-compact': compact }">
        <!-- scrim for overlay panels -->
        <div v-if="compact && (paletteOpen || inspectorOpen)" class="pstudio__scrim" @click="closeOverlays" />

        <!-- palette -->
        <div
          id="pstudio-palette"
          class="pstudio__left"
          role="region"
          aria-label="Node palette"
          :aria-hidden="compact && !paletteOpen"
          :inert="compact && !paletteOpen"
          :class="{ 'is-overlay': compact, 'is-open': paletteOpen }"
          :style="compact ? {} : { width: `${leftPanel.size.value}px` }"
        >
          <NodePalette :readonly="!canEdit" @add="addPaletteNode" />
        </div>
        <div v-if="!compact" class="pstudio__resizer" @pointerdown="leftPanel.startResize" />

        <!-- canvas -->
        <div class="pstudio__center">
          <PipelineCanvas
            ref="canvasRef"
            :editor="editor"
            :readonly="!canEdit"
            :exec-statuses="execStatuses"
            :current-node-id="runner.run.value?.currentNodeId"
          />
        </div>

        <!-- inspector -->
        <div v-if="!compact" class="pstudio__resizer" @pointerdown="rightPanel.startResize" />
        <div
          id="pstudio-inspector"
          class="pstudio__right"
          role="region"
          aria-label="Node inspector"
          :aria-hidden="compact && !inspectorOpen"
          :inert="compact && !inspectorOpen"
          :class="{ 'is-overlay': compact, 'is-open': inspectorOpen }"
          :style="compact ? {} : { width: `${rightPanel.size.value}px` }"
        >
          <NodeInspector :editor="editor" :readonly="!canEdit" />
        </div>
      </div>

      <!-- bottom panel -->
      <div class="pstudio__resizer-h" @pointerdown="bottomPanel.startResize" />
      <div class="pstudio__bottom" :style="{ height: bottomOpen ? `${bottomPanel.size.value}px` : '38px' }">
        <div class="pstudio__bottom-head">
          <VipSegmented
            :model-value="bottomTab"
            :options="[
              { value: 'validation', label: `Validation${errorCount ? ` (${errorCount})` : ''}` },
              { value: 'logs', label: 'Run logs' },
              { value: 'results', label: 'Results' },
            ]"
            size="sm"
            @update:model-value="setBottomTab($event as typeof bottomTab)"
          />
          <div class="pstudio__bottom-status">
            <template v-if="runner.run.value">
              <VipBadge
                :tone="
                  runner.run.value.status === 'succeeded'
                    ? 'success'
                    : runner.run.value.status === 'failed'
                      ? 'danger'
                      : runner.run.value.status === 'running'
                        ? 'info'
                        : 'neutral'
                "
                size="sm"
                >{{ runner.run.value.status }}</VipBadge
              >
              <span class="pstudio__cid">{{ runner.run.value.correlationId }}</span>
            </template>
            <VipButton
              variant="ghost"
              size="xs"
              :icon="bottomOpen ? 'chevronDown' : 'chevronUp'"
              :title="bottomOpen ? 'Collapse results panel' : 'Expand results panel'"
              :aria-label="bottomOpen ? 'Collapse results panel' : 'Expand results panel'"
              @click="bottomOpen = !bottomOpen"
            />
          </div>
        </div>

        <div v-show="bottomOpen" class="pstudio__bottom-body">
          <!-- validation -->
          <div v-if="bottomTab === 'validation'" class="pstudio__validation">
            <div v-if="!validation?.issues.length" class="pstudio__ok">
              <VipIcon name="success" :size="16" /> No issues — pipeline is valid.
            </div>
            <template v-else>
              <div class="pstudio__val-summary">
                <VipBadge v-if="errorCount" tone="danger" size="sm">{{ errorCount }} errors</VipBadge>
                <VipBadge v-if="warnCount" tone="warning" size="sm">{{ warnCount }} warnings</VipBadge>
              </div>
              <ul class="pstudio__issues">
                <li
                  v-for="issue in validation.issues"
                  :key="issue.id"
                  class="pstudio__issue"
                  :class="`is-${issue.level}`"
                  @click="issue.nodeId && editor.selectNode(issue.nodeId)"
                >
                  <VipIcon :name="issue.level === 'error' ? 'error' : 'warning'" :size="14" />
                  <span>{{ issue.message }}</span>
                  <VipBadge tone="neutral" size="sm">{{ issue.scope }}</VipBadge>
                </li>
              </ul>
            </template>
          </div>

          <!-- logs -->
          <div v-else-if="bottomTab === 'logs'" class="pstudio__logs">
            <div v-if="!runner.run.value" class="pstudio__logs-empty">Run the pipeline to stream execution logs.</div>
            <template v-else>
              <div class="pstudio__run-meta">
                <span>Progress: {{ runner.run.value.progress }}%</span>
                <span>Rows: {{ runner.run.value.rowsProcessed.toLocaleString() }}</span>
                <span>Duration: {{ formatDuration(runner.run.value.durationMs) }}</span>
                <span>Attempt: {{ runner.run.value.attempt }}</span>
                <VipButton
                  v-if="runner.run.value.status === 'failed' && canRun"
                  variant="secondary"
                  size="xs"
                  icon="refresh"
                  title="Retry requires operator access"
                  @click="retry"
                  >Retry</VipButton
                >
              </div>
              <p v-if="runner.run.value.errorMessage" class="pstudio__run-error">
                {{ runner.run.value.errorMessage }}
              </p>
              <div class="pstudio__log-lines">
                <div v-for="(l, i) in runner.run.value.logs" :key="i" class="pstudio__log" :class="`is-${l.level}`">
                  <span class="pstudio__log-ts">{{ new Date(l.ts).toLocaleTimeString() }}</span>
                  <span class="pstudio__log-msg">{{ l.message }}</span>
                </div>
              </div>
            </template>
          </div>

          <!-- results -->
          <div v-else class="pstudio__results">
            <div v-if="!runner.run.value" class="pstudio__logs-empty">
              Run the pipeline to see node results and artifacts.
            </div>
            <template v-else>
              <div v-if="runner.run.value.nodeStates.length" class="pstudio__node-results">
                <div v-for="s in runner.run.value.nodeStates" :key="s.nodeId" class="pstudio__node-result">
                  <VipIcon
                    :name="s.status === 'succeeded' ? 'success' : s.status === 'failed' ? 'error' : 'clock'"
                    :size="13"
                    :class="s.status === 'succeeded' ? 'is-ok' : ''"
                  />
                  <span class="pstudio__nr-name">{{
                    editor?.pipeline.nodes.find((n) => n.id === s.nodeId)?.title
                  }}</span>
                  <span class="pstudio__nr-rows">{{
                    s.rows != null ? `${s.rows.toLocaleString()} rows` : 'Rows unavailable'
                  }}</span>
                  <span class="pstudio__nr-dur">{{ formatDuration(s.durationMs) }}</span>
                </div>
              </div>
              <div class="pstudio__artifacts">
                <h4 class="pstudio__artifacts-title">Artifacts</h4>
                <div v-if="artifactsLoading" class="pstudio__logs-empty">Loading artifacts…</div>
                <div v-else-if="artifactsError" class="pstudio__logs-empty">{{ artifactsError }}</div>
                <div v-else-if="!artifacts.length" class="pstudio__logs-empty">No artifacts for this run.</div>
                <ul v-else class="pstudio__artifact-list">
                  <li v-for="art in artifacts" :key="art.id" class="pstudio__artifact">
                    <div class="pstudio__artifact-meta">
                      <span class="pstudio__artifact-name">{{ art.nodeKey }}</span>
                      <span class="pstudio__artifact-type">{{ art.contentType }}</span>
                      <span>{{ (art.sizeBytes / 1024).toFixed(1) }} KB</span>
                      <span>Created {{ new Date(art.createdAt).toLocaleString() }}</span>
                      <span>Expires {{ new Date(art.expiresAt).toLocaleString() }}</span>
                    </div>
                    <VipButton
                      variant="secondary"
                      size="xs"
                      icon="download"
                      :loading="downloadingArtifactId === art.id"
                      @click="downloadArtifact(art)"
                      >Download</VipButton
                    >
                  </li>
                </ul>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pstudio {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: var(--vip-bg-canvas);
}
.pstudio.is-fullscreen {
  position: fixed;
  inset: 0;
  z-index: var(--vip-z-modal);
}

.pstudio__toolbar {
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
.pstudio__tb-left {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  min-width: 0;
}
.pstudio__title {
  min-width: 0;
}
.pstudio__name {
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-sm);
  padding: 2px 6px;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  max-width: 320px;
}
.pstudio__name:hover {
  border-color: var(--vip-border);
}
.pstudio__name:focus {
  border-color: var(--vip-brand-500);
  outline: none;
}
.pstudio__meta {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: 0 6px;
  margin-top: 2px;
}
.pstudio__ver {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  font-variant-numeric: tabular-nums;
}
.pstudio__dirty {
  font-size: var(--vip-fs-xs);
  color: var(--vip-warning-text);
}
.pstudio__readonly {
  font-size: var(--vip-fs-2xs);
  font-weight: var(--vip-fw-semibold);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vip-text-muted);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  padding: 0 6px;
}
.pstudio__saved {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
}

.pstudio__tb-right {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.pstudio__group {
  display: flex;
  align-items: center;
  gap: 2px;
  padding-right: var(--vip-sp-4);
  border-right: 1px solid var(--vip-border-subtle);
}

.pstudio__loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pstudio__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.pstudio__main {
  flex: 1;
  display: flex;
  min-height: 0;
}
.pstudio__left,
.pstudio__right {
  flex: none;
  border-right: 1px solid var(--vip-border);
  overflow: hidden;
}
.pstudio__right {
  border-right: none;
  border-left: 1px solid var(--vip-border);
}
.pstudio__center {
  flex: 1;
  min-width: 0;
  position: relative;
}

.pstudio__resizer {
  width: 5px;
  flex: none;
  cursor: col-resize;
  background: transparent;
  transition: background var(--vip-motion-fast);
  margin: 0 -2px;
  z-index: 2;
}
.pstudio__resizer:hover {
  background: var(--vip-brand-soft);
}
.pstudio__resizer-h {
  height: 5px;
  cursor: row-resize;
  background: transparent;
  transition: background var(--vip-motion-fast);
  margin: -2px 0;
  z-index: 2;
}
.pstudio__resizer-h:hover {
  background: var(--vip-brand-soft);
}

.pstudio__bottom {
  flex: none;
  background: var(--vip-surface-1);
  border-top: 1px solid var(--vip-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.pstudio__bottom-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-3) var(--vip-sp-5);
  border-bottom: 1px solid var(--vip-border-subtle);
  flex: none;
}
.pstudio__bottom-status {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.pstudio__cid {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
}
.pstudio__bottom-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--vip-sp-5);
}

.pstudio__ok {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  color: var(--vip-success-text);
  font-size: var(--vip-fs-sm);
}
.pstudio__val-summary {
  display: flex;
  gap: var(--vip-sp-3);
  margin-bottom: var(--vip-sp-4);
}
.pstudio__issues {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.pstudio__issue {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-radius: var(--vip-radius-sm);
  font-size: var(--vip-fs-sm);
  cursor: pointer;
}
.pstudio__issue:hover {
  background: var(--vip-surface-hover);
}
.pstudio__issue.is-error {
  color: var(--vip-danger-text);
}
.pstudio__issue.is-warning {
  color: var(--vip-warning-text);
}
.pstudio__issue span {
  flex: 1;
}

.pstudio__run-error {
  margin: var(--vip-sp-3) 0;
  color: var(--vip-danger);
  font-size: var(--vip-fs-sm);
}
.pstudio__artifacts {
  margin-top: var(--vip-sp-5);
}
.pstudio__artifacts-title {
  margin: 0 0 var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
}
.pstudio__artifact-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.pstudio__artifact {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.pstudio__artifact-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.pstudio__artifact-name {
  color: var(--vip-text-primary);
  font-weight: var(--vip-fw-medium);
}
.pstudio__artifact-type {
  font-family: var(--vip-font-mono);
}
.pstudio__logs-empty {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.pstudio__run-meta {
  display: flex;
  gap: var(--vip-sp-6);
  align-items: center;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
  margin-bottom: var(--vip-sp-4);
  font-variant-numeric: tabular-nums;
}
.pstudio__log-lines {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-xs);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.pstudio__log {
  display: flex;
  gap: var(--vip-sp-4);
}
.pstudio__log-ts {
  color: var(--vip-text-disabled);
  flex: none;
}
.pstudio__log.is-error .pstudio__log-msg {
  color: var(--vip-danger-text);
}
.pstudio__log.is-warn .pstudio__log-msg {
  color: var(--vip-warning-text);
}
.pstudio__log-msg {
  color: var(--vip-text-secondary);
}

.pstudio__node-results {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.pstudio__node-result {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-radius: var(--vip-radius-sm);
  font-size: var(--vip-fs-sm);
}
.pstudio__node-result:hover {
  background: var(--vip-surface-hover);
}
.pstudio__node-result .is-ok {
  color: var(--vip-success-text);
}
.pstudio__nr-name {
  flex: 1;
}
.pstudio__nr-rows,
.pstudio__nr-dur {
  color: var(--vip-text-muted);
  font-variant-numeric: tabular-nums;
}

/* ---- compact / responsive (tablet + phone) ---- */
.pstudio__scrim {
  position: absolute;
  inset: 0;
  background: var(--vip-scrim);
  z-index: 8;
}
.pstudio__main.is-compact {
  position: relative;
}
.pstudio__main.is-compact .pstudio__left,
.pstudio__main.is-compact .pstudio__right {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 9;
  width: min(84vw, 320px);
  box-shadow: var(--vip-shadow-lg);
  transition: transform var(--vip-motion-base) var(--vip-ease-emphasized);
}
.pstudio__main.is-compact .pstudio__left {
  left: 0;
  transform: translateX(-101%);
}
.pstudio__main.is-compact .pstudio__right {
  right: 0;
  transform: translateX(101%);
}
.pstudio__main.is-compact .pstudio__left.is-open {
  transform: translateX(0);
}
.pstudio__main.is-compact .pstudio__right.is-open {
  transform: translateX(0);
}

@media (max-width: 899px) {
  .pstudio__toolbar {
    flex-wrap: wrap;
    height: auto;
    min-height: 52px;
    padding: var(--vip-sp-3) var(--vip-sp-4);
    gap: var(--vip-sp-3);
  }
  .pstudio__tb-right {
    flex-wrap: wrap;
    gap: var(--vip-sp-2);
  }
  .pstudio__group {
    padding-right: var(--vip-sp-2);
  }
  .pstudio__name {
    max-width: 40vw;
  }
}
@media (max-width: 599px) {
  .pstudio__tb-left {
    min-width: 0;
    flex: 1;
  }
  .pstudio__meta {
    display: none;
  }
}
</style>
