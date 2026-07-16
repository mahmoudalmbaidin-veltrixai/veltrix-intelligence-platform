<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime } from '@/shared/lib/format'
import { isoAgo, nowIso } from '@/shared/lib/mock'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { reportService, type ReportStatus } from './reports.service'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipTooltip from '@/shared/ui/VipTooltip.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('report:write'))

const reportId = computed(() => (route.params.id ? String(route.params.id) : null))
const isNew = computed(() => reportId.value === null)

const { data: loaded } = useQuery(
  () => `report:${reportId.value ?? 'new'}`,
  async () => (reportId.value ? await reportService.get(reportId.value) : undefined),
)

const name = ref('Untitled report')
const status = ref<ReportStatus>('draft')
const reviewers = ref<string[]>(['Finance', 'Legal'])

watch(loaded, (r) => {
  if (r) {
    name.value = r.name
    status.value = r.status
    reviewers.value = r.reviewers.length ? [...r.reviewers] : reviewers.value
  }
})

/* ---- block palette + document ---- */
type BlockKind = 'cover' | 'header' | 'footer' | 'text' | 'table' | 'chart' | 'kpi' | 'image' | 'pagebreak' | 'section'
interface PaletteItem { kind: BlockKind; label: string; icon: string }
const palette: PaletteItem[] = [
  { kind: 'cover', label: 'Cover', icon: 'image' },
  { kind: 'header', label: 'Header', icon: 'panelBottom' },
  { kind: 'footer', label: 'Footer', icon: 'panelBottom' },
  { kind: 'section', label: 'Section', icon: 'folder' },
  { kind: 'text', label: 'Text', icon: 'text' },
  { kind: 'table', label: 'Table', icon: 'table' },
  { kind: 'chart', label: 'Chart', icon: 'chart' },
  { kind: 'kpi', label: 'KPI block', icon: 'gauge' },
  { kind: 'image', label: 'Image', icon: 'image' },
  { kind: 'pagebreak', label: 'Page break', icon: 'minus' },
]

interface Block { id: string; kind: BlockKind; title: string; binding: string }
const BLOCK_META: Record<BlockKind, { icon: string; label: string; defaultTitle: string; binding: string }> = {
  cover: { icon: 'image', label: 'Cover', defaultTitle: 'Report cover', binding: 'Static — title, logo, period' },
  header: { icon: 'panelBottom', label: 'Header', defaultTitle: 'Page header', binding: 'Static — running header' },
  footer: { icon: 'panelBottom', label: 'Footer', defaultTitle: 'Page footer', binding: 'Static — page number, date' },
  section: { icon: 'folder', label: 'Section', defaultTitle: 'New section', binding: 'Grouping only' },
  text: { icon: 'text', label: 'Text', defaultTitle: 'Narrative text', binding: 'Rich text' },
  table: { icon: 'table', label: 'Table', defaultTitle: 'Data table', binding: 'Semantic query · Sales Analytics' },
  chart: { icon: 'chart', label: 'Chart', defaultTitle: 'Trend chart', binding: 'Semantic query · Revenue by month' },
  kpi: { icon: 'gauge', label: 'KPI block', defaultTitle: 'Headline KPIs', binding: 'Metrics · Net Revenue, Margin' },
  image: { icon: 'image', label: 'Image', defaultTitle: 'Image', binding: 'Uploaded asset' },
  pagebreak: { icon: 'minus', label: 'Page break', defaultTitle: 'Page break', binding: 'Layout only' },
}

let blockSeq = 0
function makeBlock(kind: BlockKind): Block {
  const meta = BLOCK_META[kind]
  return { id: `blk_${blockSeq++}`, kind, title: meta.defaultTitle, binding: meta.binding }
}

const blocks = reactive<Block[]>([
  makeBlock('cover'),
  makeBlock('kpi'),
  makeBlock('chart'),
  makeBlock('table'),
])

const selectedId = ref<string | null>(blocks[0]?.id ?? null)
const selected = computed(() => blocks.find((b) => b.id === selectedId.value) ?? null)

function addBlock(kind: BlockKind) {
  const b = makeBlock(kind)
  blocks.push(b)
  selectedId.value = b.id
}
function moveUp(i: number) {
  if (i <= 0) return
  const [b] = blocks.splice(i, 1)
  blocks.splice(i - 1, 0, b)
}
function moveDown(i: number) {
  if (i >= blocks.length - 1) return
  const [b] = blocks.splice(i, 1)
  blocks.splice(i + 1, 0, b)
}
function removeBlock(i: number) {
  const [removed] = blocks.splice(i, 1)
  if (selectedId.value === removed.id) selectedId.value = blocks[0]?.id ?? null
}

/* ---- report parameters ---- */
interface Param { id: string; label: string; value: string }
const params = reactive<Param[]>([
  { id: 'p_period', label: 'Reporting period', value: 'Q3 2026' },
  { id: 'p_region', label: 'Region', value: 'All regions' },
  { id: 'p_currency', label: 'Currency', value: 'USD' },
])

/* ---- preview mode ---- */
const mode = ref<'edit' | 'print'>('edit')
const modeOptions = [
  { value: 'edit' as const, label: 'Edit', icon: 'code' },
  { value: 'print' as const, label: 'Print / PDF', icon: 'eye' },
]

/* ---- workflow ---- */
const STATUS_TONE: Record<ReportStatus, 'neutral' | 'warning' | 'info' | 'success' | 'danger'> = {
  draft: 'neutral', 'in-review': 'warning', approved: 'info', published: 'success', rejected: 'danger',
}
const STATUS_LABEL: Record<ReportStatus, string> = {
  draft: 'Draft', 'in-review': 'In review', approved: 'Approved', published: 'Published', rejected: 'Rejected',
}
const workflowSteps: { key: ReportStatus; label: string }[] = [
  { key: 'draft', label: 'Draft' },
  { key: 'in-review', label: 'In review' },
  { key: 'approved', label: 'Approved' },
  { key: 'published', label: 'Published' },
]
const stepIndex = computed(() => {
  const order: ReportStatus[] = ['draft', 'in-review', 'approved', 'published']
  const idx = order.indexOf(status.value === 'rejected' ? 'in-review' : status.value)
  return idx < 0 ? 0 : idx
})

const drawerOpen = ref(false)
const comment = ref('')

interface Decision { id: string; actor: string; decision: string; comment: string; when: string }
const history = reactive<Decision[]>([
  { id: 'h1', actor: 'A. Rahman', decision: 'Submitted for review', comment: 'Draft complete, figures reconciled to ledger.', when: isoAgo(60 * 6) },
  { id: 'h2', actor: 'Finance', decision: 'Comment', comment: 'Please add a YoY comparison to the revenue chart.', when: isoAgo(60 * 4) },
])

let decisionSeq = 0
function record(decision: string) {
  history.unshift({
    id: `hn_${decisionSeq++}`,
    actor: platform.user.name,
    decision,
    comment: comment.value.trim() || '—',
    when: nowIso(),
  })
  comment.value = ''
}

function saveDraft() {
  status.value = 'draft'
  ui.pushToast({ kind: 'success', title: 'Draft saved', message: `${name.value} saved.` })
}
function submitForReview() {
  if (!blocks.length) {
    ui.pushToast({ kind: 'warning', title: 'Nothing to review', message: 'Add at least one block before submitting.' })
    return
  }
  status.value = 'in-review'
  record('Submitted for review')
  ui.pushToast({ kind: 'info', title: 'Submitted', message: 'Reviewers have been notified.' })
}
function approve() {
  status.value = 'approved'
  record('Approved')
  ui.pushToast({ kind: 'success', title: 'Approved', message: `${name.value} approved for publishing.` })
}
function reject() {
  status.value = 'rejected'
  record('Rejected')
  ui.pushToast({ kind: 'warning', title: 'Rejected', message: 'Returned to the author with comments.' })
}
function publish() {
  if (status.value !== 'approved') {
    ui.pushToast({ kind: 'warning', title: 'Approval required', message: 'The report must be approved before publishing.' })
    return
  }
  status.value = 'published'
  record('Published')
  ui.pushToast({ kind: 'success', title: 'Published', message: `${name.value} is live.` })
}

function exit() {
  router.push('/reports')
}
</script>

<template>
  <div class="studio">
    <!-- Top toolbar (own chrome for full-bleed studio route) -->
    <header class="toolbar">
      <div class="toolbar__left">
        <VipButton variant="ghost" icon="chevronLeft" size="sm" @click="exit">Reports</VipButton>
        <span class="toolbar__sep" />
        <VipIcon name="report" :size="16" class="toolbar__doc-icon" />
        <input v-model="name" class="toolbar__name" :disabled="!canWrite" aria-label="Report name" />
        <VipBadge :tone="STATUS_TONE[status]" variant="soft" size="sm">{{ STATUS_LABEL[status] }}</VipBadge>
        <VipBadge v-if="isNew" tone="brand" variant="outline" size="sm">New</VipBadge>
      </div>
      <div class="toolbar__right">
        <VipSegmented v-model="mode" :options="modeOptions" size="sm" />
        <span class="toolbar__sep" />
        <VipButton variant="tertiary" icon="workflow" size="sm" @click="drawerOpen = true">Approval</VipButton>
        <VipButton variant="secondary" icon="save" size="sm" :disabled="!canWrite" @click="saveDraft">Save draft</VipButton>
        <VipButton
          v-if="status === 'draft' || status === 'rejected'"
          variant="secondary"
          size="sm"
          :disabled="!canWrite"
          @click="submitForReview"
        >Submit for review</VipButton>
        <VipButton
          variant="primary"
          icon="check"
          size="sm"
          :disabled="!canWrite || status !== 'approved'"
          @click="publish"
        >Publish</VipButton>
      </div>
    </header>

    <div class="body">
      <!-- LEFT: block palette -->
      <aside class="palette">
        <div class="palette__head">Blocks</div>
        <div class="palette__grid">
          <button
            v-for="p in palette"
            :key="p.kind"
            type="button"
            class="palette__item"
            :disabled="!canWrite"
            @click="addBlock(p.kind)"
          >
            <VipIcon :name="p.icon" :size="16" />
            <span>{{ p.label }}</span>
          </button>
        </div>
        <p class="palette__hint">Click a block to append it to the document.</p>
      </aside>

      <!-- CENTER: document canvas -->
      <main class="canvas" :class="{ 'is-print': mode === 'print' }">
        <div class="page">
          <div v-if="!blocks.length" class="page__empty">
            <VipEmptyState icon="report" title="Empty document" description="Add blocks from the palette to build your report." />
          </div>
          <div
            v-for="(b, i) in blocks"
            v-else
            :key="b.id"
            class="block"
            :class="[`block--${b.kind}`, { 'is-selected': b.id === selectedId && mode === 'edit' }]"
            @click="selectedId = b.id"
          >
            <div v-if="mode === 'edit'" class="block__bar">
              <span class="block__kind"><VipIcon :name="BLOCK_META[b.kind].icon" :size="12" /> {{ BLOCK_META[b.kind].label }}</span>
              <div class="block__tools" @click.stop>
                <VipTooltip text="Move up"><button type="button" class="tool" :disabled="i === 0" @click="moveUp(i)"><VipIcon name="chevronUp" :size="13" /></button></VipTooltip>
                <VipTooltip text="Move down"><button type="button" class="tool" :disabled="i === blocks.length - 1" @click="moveDown(i)"><VipIcon name="chevronDown" :size="13" /></button></VipTooltip>
                <VipTooltip text="Delete"><button type="button" class="tool tool--danger" @click="removeBlock(i)"><VipIcon name="trash" :size="13" /></button></VipTooltip>
              </div>
            </div>

            <!-- block previews -->
            <div v-if="b.kind === 'pagebreak'" class="pb"><span>Page break</span></div>
            <div v-else-if="b.kind === 'cover'" class="cover">
              <div class="cover__eyebrow">{{ params[0].value }}</div>
              <div class="cover__title">{{ b.title }}</div>
              <div class="cover__owner">Prepared by {{ platform.user.name }}</div>
            </div>
            <div v-else-if="b.kind === 'kpi'" class="kpi">
              <div class="kpi__title">{{ b.title }}</div>
              <div class="kpi__row">
                <div v-for="k in ['Net Revenue', 'Gross Margin', 'Orders']" :key="k" class="kpi__tile">
                  <div class="kpi__label">{{ k }}</div>
                  <div class="kpi__value">••••</div>
                </div>
              </div>
            </div>
            <div v-else-if="b.kind === 'chart'" class="chart">
              <div class="chart__title">{{ b.title }}</div>
              <div class="chart__bars">
                <span v-for="n in 12" :key="n" :style="{ height: `${25 + ((n * 37) % 70)}%` }" />
              </div>
            </div>
            <div v-else-if="b.kind === 'table'" class="tbl">
              <div class="tbl__title">{{ b.title }}</div>
              <div class="tbl__grid">
                <div v-for="n in 16" :key="n" class="tbl__cell" :class="{ 'is-head': n <= 4 }" />
              </div>
            </div>
            <div v-else-if="b.kind === 'section'" class="section">{{ b.title }}</div>
            <div v-else-if="b.kind === 'header'" class="hf hf--head">{{ b.title }} · {{ name }}</div>
            <div v-else-if="b.kind === 'footer'" class="hf hf--foot">{{ b.title }} · Page 1 · Confidential</div>
            <div v-else-if="b.kind === 'image'" class="img"><VipIcon name="image" :size="22" /><span>{{ b.title }}</span></div>
            <div v-else class="text">
              <div class="text__title">{{ b.title }}</div>
              <div class="text__lines"><span v-for="n in 4" :key="n" :style="{ width: `${100 - n * 8}%` }" /></div>
            </div>
          </div>
        </div>
      </main>

      <!-- RIGHT: inspector -->
      <aside class="inspector">
        <div class="inspector__head">Inspector</div>
        <div class="inspector__body">
          <template v-if="selected">
            <div class="inspector__section-title">Selected block</div>
            <VipInput :model-value="selected.title" label="Block title" :disabled="!canWrite" @update:model-value="(v) => (selected!.title = String(v))" />
            <VipInput :model-value="selected.binding" label="Data binding" :disabled="!canWrite" help="Where this block sources its content." @update:model-value="(v) => (selected!.binding = String(v))" />
            <div class="inspector__kind">
              <VipIcon :name="BLOCK_META[selected.kind].icon" :size="13" />
              {{ BLOCK_META[selected.kind].label }} block
            </div>
          </template>
          <div v-else class="inspector__none">Select a block to edit its properties.</div>

          <div class="inspector__divider" />

          <div class="inspector__section-title">Report parameters</div>
          <div class="params">
            <VipInput
              v-for="p in params"
              :key="p.id"
              :model-value="p.value"
              :label="p.label"
              size="sm"
              :disabled="!canWrite"
              @update:model-value="(v) => (p.value = String(v))"
            />
          </div>

          <div class="inspector__divider" />
          <div class="inspector__section-title">Output</div>
          <div class="inspector__mode">
            <span>{{ mode === 'print' ? 'Print / PDF preview' : 'Editing layout' }}</span>
            <VipBadge tone="neutral" variant="soft" size="sm">{{ blocks.length }} blocks</VipBadge>
          </div>
        </div>
      </aside>
    </div>

    <!-- Approval workflow drawer -->
    <VipDrawer :open="drawerOpen" title="Approval workflow" :width="440" @close="drawerOpen = false">
      <div class="wf">
        <ol class="wf__steps">
          <li
            v-for="(s, i) in workflowSteps"
            :key="s.key"
            class="wf__step"
            :class="{ 'is-done': i < stepIndex, 'is-active': i === stepIndex && status !== 'rejected', 'is-rejected': status === 'rejected' && s.key === 'in-review' }"
          >
            <span class="wf__dot"><VipIcon :name="i < stepIndex ? 'check' : 'circle'" :size="11" /></span>
            <span class="wf__label">{{ s.label }}</span>
          </li>
        </ol>

        <div v-if="status === 'rejected'" class="wf__rejected">
          <VipIcon name="error" :size="14" /> This report was rejected and returned to the author.
        </div>

        <div class="wf__block">
          <div class="wf__title">Reviewers</div>
          <div class="wf__reviewers">
            <VipBadge v-for="r in reviewers" :key="r" tone="info" variant="soft" size="sm">{{ r }}</VipBadge>
            <span v-if="!reviewers.length" class="wf__muted">No reviewers assigned.</span>
          </div>
        </div>

        <div class="wf__block">
          <VipTextarea v-model="comment" label="Decision comment" :rows="3" placeholder="Add context for your decision…" />
          <div class="wf__actions">
            <VipButton
              variant="secondary"
              size="sm"
              :disabled="!canWrite || status !== 'in-review'"
              @click="reject"
            >Reject</VipButton>
            <VipButton
              variant="primary"
              size="sm"
              :disabled="!canWrite || status !== 'in-review'"
              @click="approve"
            >Approve</VipButton>
          </div>
        </div>

        <div class="wf__block">
          <div class="wf__title">Decision history</div>
          <ul class="wf__history">
            <li v-for="h in history" :key="h.id" class="wf__hist">
              <div class="wf__hist-row">
                <span class="wf__hist-actor">{{ h.actor }}</span>
                <span class="wf__hist-decision">{{ h.decision }}</span>
                <span class="wf__hist-time">{{ relativeTime(h.when) }}</span>
              </div>
              <div class="wf__hist-comment">{{ h.comment }}</div>
            </li>
          </ul>
        </div>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="drawerOpen = false">Close</VipButton>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.studio { display: flex; flex-direction: column; height: 100vh; background: var(--vip-bg-canvas); }

.toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-6);
  padding: var(--vip-sp-4) var(--vip-sp-6);
  background: var(--vip-surface-1); border-bottom: 1px solid var(--vip-border); flex: none;
}
.toolbar__left, .toolbar__right { display: flex; align-items: center; gap: var(--vip-sp-4); min-width: 0; }
.toolbar__sep { width: 1px; height: 20px; background: var(--vip-border); }
.toolbar__doc-icon { color: var(--vip-text-muted); }
.toolbar__name {
  background: none; border: 1px solid transparent; border-radius: var(--vip-radius-sm);
  color: var(--vip-text-primary); font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold);
  padding: var(--vip-sp-2) var(--vip-sp-4); min-width: 120px; max-width: 320px; outline: none;
}
.toolbar__name:hover { background: var(--vip-surface-hover); }
.toolbar__name:focus { border-color: var(--vip-brand-500); background: var(--vip-surface-2); }

.body { flex: 1; display: grid; grid-template-columns: 200px 1fr 288px; min-height: 0; }

.palette { background: var(--vip-surface-1); border-right: 1px solid var(--vip-border); overflow-y: auto; }
.palette__head, .inspector__head { padding: var(--vip-sp-5) var(--vip-sp-6); font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); font-weight: var(--vip-fw-semibold); border-bottom: 1px solid var(--vip-border-subtle); }
.palette__grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-3); padding: var(--vip-sp-4); }
.palette__item {
  display: flex; flex-direction: column; align-items: center; gap: var(--vip-sp-3);
  padding: var(--vip-sp-5) var(--vip-sp-3); background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary); font-size: var(--vip-fs-xs); cursor: pointer;
}
.palette__item:hover:not(:disabled) { background: var(--vip-surface-hover); border-color: var(--vip-border-strong); color: var(--vip-text-primary); }
.palette__item:disabled { opacity: 0.5; cursor: not-allowed; }
.palette__hint { padding: var(--vip-sp-3) var(--vip-sp-6) var(--vip-sp-6); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }

.canvas { overflow-y: auto; padding: var(--vip-sp-8); display: flex; justify-content: center; }
.page {
  width: 100%; max-width: 720px; min-height: 900px;
  background: var(--vip-surface-1); border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-sm); box-shadow: var(--vip-shadow-md);
  padding: var(--vip-sp-7); display: flex; flex-direction: column; gap: var(--vip-sp-5); height: fit-content;
}
.canvas.is-print .page { box-shadow: var(--vip-shadow-lg); }
.page__empty { margin: auto; }

.block { border: 1px solid transparent; border-radius: var(--vip-radius-md); padding: var(--vip-sp-3); cursor: pointer; }
.canvas:not(.is-print) .block:hover { border-color: var(--vip-border); }
.block.is-selected { border-color: var(--vip-brand-500); box-shadow: 0 0 0 3px var(--vip-brand-soft); }
.block__bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--vip-sp-3); }
.block__kind { display: inline-flex; align-items: center; gap: var(--vip-sp-2); font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-disabled); }
.block__tools { display: flex; gap: 2px; }
.tool { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; background: none; border: none; border-radius: var(--vip-radius-sm); color: var(--vip-text-muted); cursor: pointer; }
.tool:hover:not(:disabled) { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.tool:disabled { opacity: 0.35; cursor: not-allowed; }
.tool--danger:hover:not(:disabled) { background: var(--vip-danger-soft); color: var(--vip-danger-text); }

.cover { padding: var(--vip-sp-9) var(--vip-sp-7); background: var(--vip-surface-2); border-radius: var(--vip-radius-md); }
.cover__eyebrow { font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-brand-text); }
.cover__title { font-size: var(--vip-fs-3xl); font-weight: var(--vip-fw-bold); color: var(--vip-text-primary); margin-top: var(--vip-sp-4); }
.cover__owner { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); margin-top: var(--vip-sp-5); }

.kpi__title, .chart__title, .tbl__title, .text__title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); margin-bottom: var(--vip-sp-4); }
.kpi__row { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--vip-sp-4); }
.kpi__tile { background: var(--vip-surface-2); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); padding: var(--vip-sp-5); }
.kpi__label { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.kpi__value { font-size: var(--vip-fs-xl); font-weight: var(--vip-fw-bold); color: var(--vip-text-primary); letter-spacing: 2px; }

.chart__bars { display: flex; align-items: flex-end; gap: var(--vip-sp-3); height: 120px; padding: var(--vip-sp-4); background: var(--vip-surface-2); border-radius: var(--vip-radius-md); }
.chart__bars span { flex: 1; background: var(--vip-brand-500); border-radius: var(--vip-radius-xs) var(--vip-radius-xs) 0 0; opacity: 0.8; }

.tbl__grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--vip-border-subtle); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-sm); overflow: hidden; }
.tbl__cell { height: 22px; background: var(--vip-surface-1); }
.tbl__cell.is-head { background: var(--vip-surface-3); }

.section { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); padding: var(--vip-sp-4) 0; border-bottom: 2px solid var(--vip-brand-500); }
.hf { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); padding: var(--vip-sp-3) 0; }
.hf--head { border-bottom: 1px solid var(--vip-border); }
.hf--foot { border-top: 1px solid var(--vip-border); text-align: center; }
.img { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--vip-sp-3); height: 140px; background: var(--vip-surface-2); border: 1px dashed var(--vip-border-strong); border-radius: var(--vip-radius-md); color: var(--vip-text-muted); font-size: var(--vip-fs-sm); }
.pb { text-align: center; color: var(--vip-text-disabled); font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); border-top: 1px dashed var(--vip-border-strong); border-bottom: 1px dashed var(--vip-border-strong); padding: var(--vip-sp-3); }
.text__lines { display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.text__lines span { height: 8px; background: var(--vip-surface-3); border-radius: var(--vip-radius-full); }

.inspector { background: var(--vip-surface-1); border-left: 1px solid var(--vip-border); overflow-y: auto; }
.inspector__body { padding: var(--vip-sp-6); display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.inspector__section-title { font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); }
.inspector__none { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.inspector__kind { display: inline-flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-xs); color: var(--vip-text-secondary); background: var(--vip-surface-2); padding: var(--vip-sp-3) var(--vip-sp-4); border-radius: var(--vip-radius-sm); width: fit-content; }
.inspector__divider { height: 1px; background: var(--vip-border-subtle); }
.params { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.inspector__mode { display: flex; align-items: center; justify-content: space-between; font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }

.wf { display: flex; flex-direction: column; gap: var(--vip-sp-7); }
.wf__steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.wf__step { display: flex; align-items: center; gap: var(--vip-sp-4); color: var(--vip-text-muted); font-size: var(--vip-fs-sm); }
.wf__dot { width: 22px; height: 22px; flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--vip-surface-3); color: var(--vip-text-disabled); }
.wf__step.is-done .wf__dot { background: var(--vip-success-soft); color: var(--vip-success-text); }
.wf__step.is-done { color: var(--vip-text-secondary); }
.wf__step.is-active .wf__dot { background: var(--vip-brand-500); color: #fff; }
.wf__step.is-active { color: var(--vip-text-primary); font-weight: var(--vip-fw-medium); }
.wf__step.is-rejected .wf__dot { background: var(--vip-danger-soft); color: var(--vip-danger-text); }
.wf__rejected { display: flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-sm); color: var(--vip-danger-text); background: var(--vip-danger-soft); padding: var(--vip-sp-4) var(--vip-sp-5); border-radius: var(--vip-radius-md); }
.wf__block { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.wf__title { font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); }
.wf__reviewers { display: flex; flex-wrap: wrap; gap: var(--vip-sp-3); }
.wf__muted { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.wf__actions { display: flex; justify-content: flex-end; gap: var(--vip-sp-4); }
.wf__history { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.wf__hist { border-left: 2px solid var(--vip-border); padding-left: var(--vip-sp-5); }
.wf__hist-row { display: flex; align-items: center; gap: var(--vip-sp-3); flex-wrap: wrap; }
.wf__hist-actor { font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); }
.wf__hist-decision { font-size: var(--vip-fs-xs); color: var(--vip-brand-text); }
.wf__hist-time { font-size: var(--vip-fs-xs); color: var(--vip-text-disabled); margin-left: auto; }
.wf__hist-comment { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); margin-top: 2px; }
</style>
