<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const router = useRouter()

/* ---- graph model ---- */
type Stage = 'source' | 'pipeline' | 'dataset' | 'semantic' | 'dashboard'

interface LineageNode {
  id: string
  label: string
  stage: Stage
  detail: string
}
interface Edge {
  from: string
  to: string
}

const STAGES: { key: Stage; label: string; icon: string }[] = [
  { key: 'source', label: 'Sources', icon: 'plug' },
  { key: 'pipeline', label: 'Pipelines', icon: 'workflow' },
  { key: 'dataset', label: 'Datasets', icon: 'database' },
  { key: 'semantic', label: 'Semantic Models', icon: 'layers' },
  { key: 'dashboard', label: 'Dashboards', icon: 'chart' },
]

const NODES: LineageNode[] = [
  { id: 'src_pg', label: 'Core Warehouse', stage: 'source', detail: 'PostgreSQL connection' },
  { id: 'src_erp', label: 'ERP (SQL Server)', stage: 'source', detail: 'SQL Server connection' },
  { id: 'src_s3', label: 'Data Lake (S3)', stage: 'source', detail: 'S3 object storage' },

  { id: 'pl_revenue', label: 'Revenue ETL', stage: 'pipeline', detail: 'Nightly incremental build' },
  { id: 'pl_events', label: 'Events Staging', stage: 'pipeline', detail: 'Streaming micro-batch' },

  { id: 'ds_orders', label: 'fct_orders', stage: 'dataset', detail: '1.28M rows · certified' },
  { id: 'ds_customers', label: 'dim_customers', stage: 'dataset', detail: '84K rows · PII' },
  { id: 'ds_events', label: 'stg_web_events', stage: 'dataset', detail: '42.8M rows · building' },

  { id: 'sm_sales', label: 'Sales Analytics', stage: 'semantic', detail: 'Certified semantic model' },
  { id: 'sm_web', label: 'Web Engagement', stage: 'semantic', detail: 'Clickstream metrics' },

  { id: 'db_exec', label: 'Executive Overview', stage: 'dashboard', detail: 'Board dashboard' },
  { id: 'db_growth', label: 'Growth Dashboard', stage: 'dashboard', detail: 'Marketing funnel' },
]

const EDGES: Edge[] = [
  { from: 'src_pg', to: 'pl_revenue' },
  { from: 'src_erp', to: 'pl_revenue' },
  { from: 'src_s3', to: 'pl_events' },
  { from: 'pl_revenue', to: 'ds_orders' },
  { from: 'pl_revenue', to: 'ds_customers' },
  { from: 'pl_events', to: 'ds_events' },
  { from: 'ds_orders', to: 'sm_sales' },
  { from: 'ds_customers', to: 'sm_sales' },
  { from: 'ds_events', to: 'sm_web' },
  { from: 'sm_sales', to: 'db_exec' },
  { from: 'sm_web', to: 'db_growth' },
  { from: 'sm_sales', to: 'db_growth' },
]

/* ---- layout ---- */
const NODE_W = 150
const NODE_H = 46
const COL_GAP = 210
const ROW_GAP = 70
const MARGIN_X = 24
const MARGIN_Y = 56

interface Placed extends LineageNode {
  x: number
  y: number
  col: number
}

const placed = computed<Placed[]>(() => {
  const out: Placed[] = []
  STAGES.forEach((stage, col) => {
    const inStage = NODES.filter((n) => n.stage === stage.key)
    inStage.forEach((n, i) => {
      out.push({
        ...n,
        col,
        x: MARGIN_X + col * COL_GAP,
        y: MARGIN_Y + i * ROW_GAP,
      })
    })
  })
  return out
})

const placedById = computed<Record<string, Placed>>(() => {
  const map: Record<string, Placed> = {}
  for (const p of placed.value) map[p.id] = p
  return map
})

const maxRows = computed(() => Math.max(...STAGES.map((s) => NODES.filter((n) => n.stage === s.key).length)))
const svgWidth = computed(() => MARGIN_X * 2 + (STAGES.length - 1) * COL_GAP + NODE_W)
const svgHeight = computed(() => MARGIN_Y + maxRows.value * ROW_GAP)

interface DrawnEdge extends Edge {
  d: string
}
const edgePaths = computed<DrawnEdge[]>(() =>
  EDGES.map((e) => {
    const a = placedById.value[e.from]
    const b = placedById.value[e.to]
    const x1 = a.x + NODE_W
    const y1 = a.y + NODE_H / 2
    const x2 = b.x
    const y2 = b.y + NODE_H / 2
    const mx = (x1 + x2) / 2
    return { ...e, d: `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}` }
  }),
)

/* ---- interaction ---- */
const selectedId = ref<string>('ds_orders')

const upstream = computed<Placed[]>(() =>
  EDGES.filter((e) => e.to === selectedId.value).map((e) => placedById.value[e.from]),
)
const downstream = computed<Placed[]>(() =>
  EDGES.filter((e) => e.from === selectedId.value).map((e) => placedById.value[e.to]),
)
const selectedNode = computed<Placed | undefined>(() => placedById.value[selectedId.value])

const connectedIds = computed<Set<string>>(() => {
  const set = new Set<string>([selectedId.value])
  for (const n of upstream.value) set.add(n.id)
  for (const n of downstream.value) set.add(n.id)
  return set
})

function isEdgeActive(e: Edge): boolean {
  return e.from === selectedId.value || e.to === selectedId.value
}
function stageIcon(stage: Stage): string {
  return STAGES.find((s) => s.key === stage)?.icon ?? 'circle'
}
function stageLabel(stage: Stage): string {
  return STAGES.find((s) => s.key === stage)?.label ?? stage
}
function select(id: string) {
  selectedId.value = id
}
</script>

<template>
  <div class="dlg">
    <VipPageHeader
      title="Data lineage"
      description="Trace how data flows from sources through pipelines, datasets and models into dashboards."
    >
      <template #actions>
        <VipButton variant="tertiary" icon="chevronLeft" @click="router.push('/datasets')">Back to datasets</VipButton>
      </template>
    </VipPageHeader>

    <div class="dlg__layout">
      <VipCard class="dlg__graph-card" :padded="false">
        <div class="dlg__stage-heads">
          <div v-for="s in STAGES" :key="s.key" class="dlg__stage-head">
            <VipIcon :name="s.icon" :size="14" />
            <span>{{ s.label }}</span>
          </div>
        </div>
        <div class="dlg__graph-scroll">
          <svg
            class="dlg__svg"
            :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
            :width="svgWidth"
            :height="svgHeight"
            role="img"
            aria-label="Data lineage graph"
          >
            <!-- edges -->
            <path
              v-for="(e, i) in edgePaths"
              :key="`e-${i}`"
              :d="e.d"
              class="dlg__edge"
              :class="{ 'is-active': isEdgeActive(e) }"
              fill="none"
            />
            <!-- nodes -->
            <g
              v-for="n in placed"
              :key="n.id"
              class="dlg__node"
              :class="{
                'is-selected': n.id === selectedId,
                'is-connected': connectedIds.has(n.id) && n.id !== selectedId,
                'is-dim': !connectedIds.has(n.id),
              }"
              :transform="`translate(${n.x}, ${n.y})`"
              role="button"
              :aria-label="`${stageLabel(n.stage)}: ${n.label}`"
              tabindex="0"
              @click="select(n.id)"
              @keydown.enter="select(n.id)"
            >
              <rect class="dlg__node-rect" :width="NODE_W" :height="NODE_H" rx="8" />
              <text class="dlg__node-label" :x="12" :y="NODE_H / 2 - 3">{{ n.label }}</text>
              <text class="dlg__node-detail" :x="12" :y="NODE_H / 2 + 12">{{ n.detail }}</text>
            </g>
          </svg>
        </div>
      </VipCard>

      <!-- side panel -->
      <VipCard class="dlg__panel">
        <template v-if="selectedNode">
          <div class="dlg__panel-head">
            <span class="dlg__panel-icon"><VipIcon :name="stageIcon(selectedNode.stage)" :size="18" /></span>
            <div>
              <h3 class="dlg__panel-title">{{ selectedNode.label }}</h3>
              <VipBadge tone="brand" variant="soft" size="sm">{{ stageLabel(selectedNode.stage) }}</VipBadge>
            </div>
          </div>
          <p class="dlg__panel-detail">{{ selectedNode.detail }}</p>

          <div class="dlg__rel">
            <span class="dlg__rel-title">Upstream ({{ upstream.length }})</span>
            <ul v-if="upstream.length" class="dlg__rel-list">
              <li v-for="u in upstream" :key="u.id" @click="select(u.id)">
                <VipIcon :name="stageIcon(u.stage)" :size="13" />{{ u.label }}
              </li>
            </ul>
            <p v-else class="dlg__rel-empty">No upstream dependencies — this is a source.</p>
          </div>

          <div class="dlg__rel">
            <span class="dlg__rel-title">Downstream ({{ downstream.length }})</span>
            <ul v-if="downstream.length" class="dlg__rel-list">
              <li v-for="d in downstream" :key="d.id" @click="select(d.id)">
                <VipIcon :name="stageIcon(d.stage)" :size="13" />{{ d.label }}
              </li>
            </ul>
            <p v-else class="dlg__rel-empty">No downstream consumers.</p>
          </div>
        </template>
      </VipCard>
    </div>

    <!-- accessible list fallback -->
    <VipCard class="dlg__fallback">
      <h3 class="dlg__fallback-title">Lineage as a list</h3>
      <p class="dlg__muted">A text description of every node and its immediate dependencies.</p>
      <dl class="dlg__fallback-list">
        <div v-for="n in placed" :key="`fb-${n.id}`" class="dlg__fallback-row">
          <dt>
            <VipIcon :name="stageIcon(n.stage)" :size="13" />
            {{ n.label }}
            <span class="dlg__fallback-stage">{{ stageLabel(n.stage) }}</span>
          </dt>
          <dd>
            <span class="dlg__fallback-dep">
              Upstream:
              <template v-if="EDGES.some((e) => e.to === n.id)">
                {{
                  EDGES.filter((e) => e.to === n.id)
                    .map((e) => placedById[e.from].label)
                    .join(', ')
                }}
              </template>
              <template v-else>none</template>
            </span>
            <span class="dlg__fallback-dep">
              Downstream:
              <template v-if="EDGES.some((e) => e.from === n.id)">
                {{
                  EDGES.filter((e) => e.from === n.id)
                    .map((e) => placedById[e.to].label)
                    .join(', ')
                }}
              </template>
              <template v-else>none</template>
            </span>
          </dd>
        </div>
      </dl>
    </VipCard>
  </div>
</template>

<style scoped>
.dlg {
  max-width: 1280px;
  margin: 0 auto;
}
.dlg__layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--vip-sp-6);
  align-items: start;
}

.dlg__graph-card {
  overflow: hidden;
}
.dlg__stage-heads {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.dlg__stage-head {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
}
.dlg__graph-scroll {
  overflow-x: auto;
  padding: var(--vip-sp-5);
}
.dlg__svg {
  display: block;
}

.dlg__edge {
  stroke: var(--vip-border-strong);
  stroke-width: 1.5;
  transition: stroke var(--vip-motion-fast);
}
.dlg__edge.is-active {
  stroke: var(--vip-brand-500);
  stroke-width: 2.5;
}

.dlg__node {
  cursor: pointer;
  transition: opacity var(--vip-motion-fast);
}
.dlg__node-rect {
  fill: var(--vip-surface-2);
  stroke: var(--vip-border);
  stroke-width: 1.5;
  transition:
    fill var(--vip-motion-fast),
    stroke var(--vip-motion-fast);
}
.dlg__node:hover .dlg__node-rect {
  stroke: var(--vip-border-strong);
}
.dlg__node.is-selected .dlg__node-rect {
  fill: var(--vip-brand-soft);
  stroke: var(--vip-brand-500);
  stroke-width: 2;
}
.dlg__node.is-connected .dlg__node-rect {
  stroke: var(--vip-brand-400);
}
.dlg__node.is-dim {
  opacity: 0.5;
}
.dlg__node-label {
  fill: var(--vip-text-primary);
  font-size: 12px;
  font-weight: 600;
  font-family: var(--vip-font-sans);
}
.dlg__node-detail {
  fill: var(--vip-text-muted);
  font-size: 9.5px;
  font-family: var(--vip-font-sans);
}

.dlg__panel {
  position: sticky;
  top: var(--vip-sp-6);
}
.dlg__panel-head {
  display: flex;
  gap: var(--vip-sp-4);
  align-items: flex-start;
  margin-bottom: var(--vip-sp-5);
}
.dlg__panel-icon {
  width: 36px;
  height: 36px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.dlg__panel-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-3);
}
.dlg__panel-detail {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin-bottom: var(--vip-sp-6);
}
.dlg__rel {
  margin-bottom: var(--vip-sp-6);
}
.dlg__rel-title {
  display: block;
  font-size: var(--vip-fs-xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
  margin-bottom: var(--vip-sp-4);
}
.dlg__rel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.dlg__rel-list li {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-sm);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  cursor: pointer;
}
.dlg__rel-list li:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.dlg__rel-empty {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}

.dlg__fallback {
  margin-top: var(--vip-sp-6);
}
.dlg__fallback-title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.dlg__muted {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-bottom: var(--vip-sp-5);
}
.dlg__fallback-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--vip-sp-4);
  margin: 0;
}
.dlg__fallback-row {
  padding: var(--vip-sp-4) var(--vip-sp-5);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.dlg__fallback-row dt {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.dlg__fallback-stage {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
  font-weight: var(--vip-fw-regular);
  margin-left: auto;
}
.dlg__fallback-row dd {
  margin: var(--vip-sp-4) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.dlg__fallback-dep {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}

@media (max-width: 1000px) {
  .dlg__layout {
    grid-template-columns: 1fr;
  }
  .dlg__panel {
    position: static;
  }
}
</style>
