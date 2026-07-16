<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime, formatDateTime, formatNumber } from '@/shared/lib/format'
import {
  datasetService,
  type Dataset,
  type QualityRule,
  type QualityRuleStatus,
} from './datasets.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const { data: dataset, isLoading } = useQuery(
  () => `dataset:${id.value}`,
  () => datasetService.get(id.value),
)
const { data: rules } = useQuery('datasets:rules', () => datasetService.listQualityRules())

const datasetRules = computed<QualityRule[]>(() =>
  (rules.value ?? []).filter((r) => r.dataset === dataset.value?.name),
)

const tabs = [
  { value: 'overview', label: 'Overview' },
  { value: 'preview', label: 'Data preview' },
  { value: 'schema', label: 'Schema' },
  { value: 'profile', label: 'Profile' },
  { value: 'quality', label: 'Quality' },
  { value: 'lineage', label: 'Lineage' },
  { value: 'access', label: 'Access' },
  { value: 'versions', label: 'Versions' },
  { value: 'activity', label: 'Activity' },
]
const activeTab = ref('overview')

function qualityTone(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 90) return 'success'
  if (score >= 75) return 'warning'
  return 'danger'
}
const RULE_TONE: Record<QualityRuleStatus, 'success' | 'warning' | 'danger'> = {
  passing: 'success',
  warning: 'warning',
  failing: 'danger',
}

/* ---- overview stat cards ---- */
function overviewCards(d: Dataset): { label: string; value: string; icon: string }[] {
  return [
    { label: 'Owner', value: d.owner, icon: 'users' },
    { label: 'Rows', value: formatNumber(d.rowCount, { style: 'compact' }), icon: 'hash' },
    { label: 'Quality score', value: `${d.qualityScore}`, icon: 'gauge' },
    { label: 'Freshness', value: relativeTime(d.freshness), icon: 'clock' },
    { label: 'Source', value: d.source, icon: 'plug' },
    { label: 'Certification', value: d.certified ? 'Certified' : 'Uncertified', icon: 'shield' },
  ]
}

/* ---- schema (mock) ---- */
interface ColumnInfo { name: string; type: string; nullable: boolean; description: string }
const schema: ColumnInfo[] = [
  { name: 'order_id', type: 'bigint', nullable: false, description: 'Primary key' },
  { name: 'customer_id', type: 'bigint', nullable: false, description: 'FK to dim_customers' },
  { name: 'order_date', type: 'date', nullable: false, description: 'Date order was placed' },
  { name: 'amount', type: 'numeric(12,2)', nullable: false, description: 'Gross order amount' },
  { name: 'discount', type: 'numeric(12,2)', nullable: true, description: 'Applied discount' },
  { name: 'currency', type: 'char(3)', nullable: false, description: 'ISO 4217 currency code' },
  { name: 'status', type: 'varchar(24)', nullable: false, description: 'Fulfilment status' },
  { name: 'channel', type: 'varchar(24)', nullable: true, description: 'Sales channel' },
]
const schemaColumns: Column<ColumnInfo>[] = [
  { key: 'name', label: 'Column' },
  { key: 'type', label: 'Type' },
  { key: 'nullable', label: 'Nullable' },
  { key: 'description', label: 'Description' },
]

/* ---- data preview (mock) ---- */
interface PreviewRow { order_id: number; customer_id: number; amount: number; currency: string; status: string; order_date: string }
const preview: PreviewRow[] = [
  { order_id: 90211, customer_id: 4021, amount: 12480, currency: 'USD', status: 'paid', order_date: '2026-07-14' },
  { order_id: 90210, customer_id: 5530, amount: 3120, currency: 'USD', status: 'pending', order_date: '2026-07-14' },
  { order_id: 90209, customer_id: 1188, amount: 58900, currency: 'EUR', status: 'paid', order_date: '2026-07-13' },
  { order_id: 90208, customer_id: 7742, amount: 740, currency: 'GBP', status: 'refunded', order_date: '2026-07-13' },
  { order_id: 90207, customer_id: 3390, amount: 22150, currency: 'USD', status: 'paid', order_date: '2026-07-12' },
]
const previewColumns: Column<PreviewRow>[] = [
  { key: 'order_id', label: 'order_id', align: 'right' },
  { key: 'customer_id', label: 'customer_id', align: 'right' },
  { key: 'amount', label: 'amount', align: 'right', cell: (r) => formatNumber(r.amount, { decimals: 0 }) },
  { key: 'currency', label: 'currency' },
  { key: 'status', label: 'status' },
  { key: 'order_date', label: 'order_date' },
]

/* ---- profile (mock per-column stats) ---- */
interface ProfileStat { column: string; nulls: number; distinct: number; min: string; max: string }
const profile: ProfileStat[] = [
  { column: 'order_id', nulls: 0, distinct: 100, min: '1', max: '1,284,502' },
  { column: 'customer_id', nulls: 0, distinct: 66, min: '1', max: '84,213' },
  { column: 'amount', nulls: 0, distinct: 92, min: '0.00', max: '412,900.00' },
  { column: 'discount', nulls: 34, distinct: 41, min: '0.00', max: '18,400.00' },
  { column: 'currency', nulls: 0, distinct: 4, min: 'EUR', max: 'USD' },
  { column: 'status', nulls: 0, distinct: 5, min: 'cancelled', max: 'refunded' },
]

/* ---- access (mock) ---- */
interface AccessGrant { principal: string; role: string; type: string }
const access: AccessGrant[] = [
  { principal: 'Revenue Ops', role: 'Owner', type: 'team' },
  { principal: 'Analytics', role: 'Editor', type: 'workspace' },
  { principal: 'Business Viewers', role: 'Viewer', type: 'group' },
  { principal: 'analytics-service', role: 'Reader', type: 'service account' },
]

/* ---- versions (mock) ---- */
interface Version { id: string; label: string; when: string; author: string; note: string }
const versions: Version[] = [
  { id: 'v12', label: 'v12', when: relativeTime(new Date(Date.now() - 35 * 60000).toISOString()), author: 'Nightly Scheduler', note: 'Incremental refresh' },
  { id: 'v11', label: 'v11', when: '1d ago', author: 'A. Rahman', note: 'Added channel column' },
  { id: 'v10', label: 'v10', when: '9d ago', author: 'M. Almbaidin', note: 'Backfill 2024 orders' },
]

/* ---- activity (mock) ---- */
interface ActivityItem { id: string; actor: string; action: string; when: string; icon: string }
const activity: ActivityItem[] = [
  { id: 'a1', actor: 'Nightly Scheduler', action: 'refreshed the dataset', when: '35m', icon: 'run' },
  { id: 'a2', actor: 'Data Quality', action: 'ran 4 quality checks', when: '35m', icon: 'gauge' },
  { id: 'a3', actor: 'A. Rahman', action: 'certified the dataset', when: '1d', icon: 'shield' },
  { id: 'a4', actor: 'M. Almbaidin', action: 'edited the schema', when: '9d', icon: 'table' },
]
</script>

<template>
  <div class="dd">
    <div v-if="isLoading" class="dd__loading"><VipSpinner label="Loading dataset…" /></div>

    <VipEmptyState
      v-else-if="!dataset"
      icon="warning"
      tone="warning"
      title="Dataset not found"
      description="This dataset may have been removed or is outside your access scope."
    >
      <VipButton variant="primary" @click="router.push('/datasets')">Back to datasets</VipButton>
    </VipEmptyState>

    <template v-else>
      <VipPageHeader :title="dataset.name" :description="dataset.description">
        <template #status>
          <VipBadge :tone="dataset.status === 'active' ? 'success' : dataset.status === 'building' ? 'info' : 'neutral'" variant="soft">
            {{ dataset.status }}
          </VipBadge>
          <VipBadge v-if="dataset.certified" tone="brand" variant="soft">Certified</VipBadge>
          <VipBadge v-if="dataset.sensitive" tone="warning" variant="soft">Sensitive</VipBadge>
        </template>
        <template #actions>
          <VipButton variant="tertiary" icon="chevronLeft" @click="router.push('/datasets')">Back</VipButton>
          <VipButton variant="secondary" icon="lineage" @click="router.push('/datasets/lineage')">View lineage</VipButton>
        </template>
        <template #tabs>
          <VipTabs v-model="activeTab" :tabs="tabs" />
        </template>
      </VipPageHeader>

      <!-- OVERVIEW -->
      <section v-if="activeTab === 'overview'">
        <div class="dd__cards">
          <VipCard v-for="c in overviewCards(dataset)" :key="c.label" class="dd__stat">
            <span class="dd__stat-icon"><VipIcon :name="c.icon" :size="16" /></span>
            <span class="dd__stat-value">{{ c.value }}</span>
            <span class="dd__stat-label">{{ c.label }}</span>
          </VipCard>
        </div>
        <VipCard class="dd__tags-card">
          <h3 class="dd__card-title">Tags</h3>
          <div class="dd__tags">
            <VipBadge v-for="t in dataset.tags" :key="t" tone="neutral" variant="soft" size="sm">{{ t }}</VipBadge>
          </div>
        </VipCard>
      </section>

      <!-- DATA PREVIEW -->
      <VipCard v-else-if="activeTab === 'preview'" :padded="false">
        <div class="dd__preview-head">
          <span class="dd__mono">{{ dataset.name }} · first 5 rows</span>
          <VipBadge tone="neutral" variant="soft" size="sm">sample</VipBadge>
        </div>
        <VipTable :columns="previewColumns" :rows="preview" :row-key="(r) => String(r.order_id)" density="compact">
          <template #cell-status="{ row }">
            <VipBadge :tone="row.status === 'paid' ? 'success' : row.status === 'refunded' ? 'danger' : 'warning'" variant="soft" size="sm">{{ row.status }}</VipBadge>
          </template>
        </VipTable>
      </VipCard>

      <!-- SCHEMA -->
      <VipCard v-else-if="activeTab === 'schema'" :padded="false">
        <VipTable :columns="schemaColumns" :rows="schema" :row-key="(r) => r.name" density="compact">
          <template #cell-name="{ row }"><span class="dd__mono">{{ row.name }}</span></template>
          <template #cell-type="{ row }"><span class="dd__mono">{{ row.type }}</span></template>
          <template #cell-nullable="{ row }">
            <VipBadge :tone="row.nullable ? 'neutral' : 'success'" variant="soft" size="sm">{{ row.nullable ? 'nullable' : 'not null' }}</VipBadge>
          </template>
        </VipTable>
      </VipCard>

      <!-- PROFILE -->
      <VipCard v-else-if="activeTab === 'profile'">
        <h3 class="dd__card-title">Column profile</h3>
        <p class="dd__muted">Null ratio and distinct-value cardinality per column (sampled).</p>
        <ul class="dd__profile">
          <li v-for="p in profile" :key="p.column" class="dd__profile-row">
            <span class="dd__profile-name">{{ p.column }}</span>
            <div class="dd__profile-bars">
              <div class="dd__bar-group">
                <span class="dd__bar-label">nulls {{ p.nulls }}%</span>
                <div class="dd__bar-track"><div class="dd__bar dd__bar--null" :style="{ width: `${p.nulls}%` }" /></div>
              </div>
              <div class="dd__bar-group">
                <span class="dd__bar-label">distinct {{ p.distinct }}%</span>
                <div class="dd__bar-track"><div class="dd__bar dd__bar--distinct" :style="{ width: `${p.distinct}%` }" /></div>
              </div>
            </div>
            <span class="dd__profile-range">{{ p.min }} … {{ p.max }}</span>
          </li>
        </ul>
      </VipCard>

      <!-- QUALITY -->
      <VipCard v-else-if="activeTab === 'quality'">
        <div class="dd__quality-head">
          <h3 class="dd__card-title">Quality rules</h3>
          <VipBadge :tone="qualityTone(dataset.qualityScore)" variant="soft">Score {{ dataset.qualityScore }}</VipBadge>
        </div>
        <VipTable
          v-if="datasetRules.length"
          :columns="[
            { key: 'name', label: 'Rule' },
            { key: 'dimension', label: 'Dimension' },
            { key: 'severity', label: 'Severity' },
            { key: 'status', label: 'Status' },
            { key: 'passRate', label: 'Pass rate', align: 'right' },
          ]"
          :rows="datasetRules"
          :row-key="(r) => r.id"
          density="compact"
        >
          <template #cell-dimension="{ row }"><VipBadge tone="neutral" variant="soft" size="sm">{{ row.dimension }}</VipBadge></template>
          <template #cell-severity="{ row }">
            <VipBadge :tone="row.severity === 'high' ? 'danger' : row.severity === 'medium' ? 'warning' : 'neutral'" variant="soft" size="sm">{{ row.severity }}</VipBadge>
          </template>
          <template #cell-status="{ row }"><VipBadge :tone="RULE_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge></template>
          <template #cell-passRate="{ row }">{{ row.passRate }}%</template>
        </VipTable>
        <VipEmptyState v-else icon="gauge" title="No rules on this dataset" description="Attach quality rules from the Data Quality workspace." />
      </VipCard>

      <!-- LINEAGE -->
      <VipCard v-else-if="activeTab === 'lineage'">
        <h3 class="dd__card-title">Lineage</h3>
        <div class="dd__lineage">
          <div class="dd__lineage-col">
            <span class="dd__lineage-head">Upstream</span>
            <div class="dd__lineage-node"><VipIcon name="plug" :size="14" />{{ dataset.source }}</div>
            <div class="dd__lineage-node"><VipIcon name="workflow" :size="14" />Revenue Nightly ETL</div>
          </div>
          <VipIcon name="chevronRight" :size="18" class="dd__lineage-arrow" />
          <div class="dd__lineage-col">
            <span class="dd__lineage-head">This dataset</span>
            <div class="dd__lineage-node is-current"><VipIcon name="database" :size="14" />{{ dataset.name }}</div>
          </div>
          <VipIcon name="chevronRight" :size="18" class="dd__lineage-arrow" />
          <div class="dd__lineage-col">
            <span class="dd__lineage-head">Downstream</span>
            <div class="dd__lineage-node"><VipIcon name="layers" :size="14" />Sales Analytics</div>
            <div class="dd__lineage-node"><VipIcon name="chart" :size="14" />Executive Overview</div>
          </div>
        </div>
        <VipButton variant="tertiary" icon="lineage" @click="router.push('/datasets/lineage')">Open full lineage graph</VipButton>
      </VipCard>

      <!-- ACCESS -->
      <VipCard v-else-if="activeTab === 'access'" :padded="false">
        <VipTable
          :columns="[
            { key: 'principal', label: 'Principal' },
            { key: 'type', label: 'Type' },
            { key: 'role', label: 'Role', align: 'right' },
          ]"
          :rows="access"
          :row-key="(r) => r.principal"
          density="compact"
        >
          <template #cell-role="{ row }"><VipBadge tone="brand" variant="soft" size="sm">{{ row.role }}</VipBadge></template>
        </VipTable>
      </VipCard>

      <!-- VERSIONS -->
      <VipCard v-else-if="activeTab === 'versions'">
        <h3 class="dd__card-title">Version history</h3>
        <ul class="dd__versions">
          <li v-for="v in versions" :key="v.id" class="dd__version">
            <VipBadge tone="neutral" variant="outline" size="sm">{{ v.label }}</VipBadge>
            <div class="dd__version-body">
              <span class="dd__version-note">{{ v.note }}</span>
              <span class="dd__version-meta">{{ v.author }} · {{ v.when }}</span>
            </div>
          </li>
        </ul>
      </VipCard>

      <!-- ACTIVITY -->
      <VipCard v-else>
        <h3 class="dd__card-title">Recent activity</h3>
        <ul class="dd__feed">
          <li v-for="a in activity" :key="a.id" class="dd__feed-item">
            <span class="dd__feed-dot"><VipIcon :name="a.icon" :size="13" /></span>
            <div class="dd__feed-body">
              <span class="dd__feed-text"><strong>{{ a.actor }}</strong> {{ a.action }}</span>
              <span class="dd__feed-time">{{ a.when }} ago</span>
            </div>
          </li>
        </ul>
        <p class="dd__muted">Dataset created {{ formatDateTime(dataset.freshness) }} · last refreshed {{ relativeTime(dataset.freshness) }}.</p>
      </VipCard>
    </template>
  </div>
</template>

<style scoped>
.dd { max-width: 1200px; margin: 0 auto; }
.dd__loading { display: flex; justify-content: center; padding: var(--vip-sp-12); }
.dd__card-title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-5); }
.dd__muted { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.dd__mono { font-family: var(--vip-font-mono); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }

.dd__cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--vip-sp-6); }
.dd__stat { display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.dd__stat-icon { width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center; border-radius: var(--vip-radius-md); background: var(--vip-surface-3); color: var(--vip-text-secondary); }
.dd__stat-value { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); margin-top: var(--vip-sp-3); }
.dd__stat-label { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.dd__tags-card { margin-top: var(--vip-sp-6); }
.dd__tags { display: flex; flex-wrap: wrap; gap: var(--vip-sp-3); }

.dd__preview-head { display: flex; align-items: center; justify-content: space-between; padding: var(--vip-sp-5) var(--vip-sp-6); border-bottom: 1px solid var(--vip-border-subtle); }

.dd__profile { list-style: none; margin: var(--vip-sp-5) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.dd__profile-row { display: grid; grid-template-columns: 160px 1fr 200px; align-items: center; gap: var(--vip-sp-6); padding: var(--vip-sp-4) 0; border-bottom: 1px solid var(--vip-border-subtle); }
.dd__profile-name { font-family: var(--vip-font-mono); font-size: var(--vip-fs-sm); color: var(--vip-text-primary); }
.dd__profile-bars { display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.dd__bar-group { display: flex; align-items: center; gap: var(--vip-sp-4); }
.dd__bar-label { font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); width: 88px; flex: none; }
.dd__bar-track { flex: 1; height: 6px; background: var(--vip-surface-3); border-radius: var(--vip-radius-full); overflow: hidden; }
.dd__bar { height: 100%; border-radius: var(--vip-radius-full); }
.dd__bar--null { background: var(--vip-warning); }
.dd__bar--distinct { background: var(--vip-brand-500); }
.dd__profile-range { font-family: var(--vip-font-mono); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); text-align: right; }

.dd__quality-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--vip-sp-5); }

.dd__lineage { display: flex; align-items: stretch; gap: var(--vip-sp-6); margin-bottom: var(--vip-sp-6); overflow-x: auto; }
.dd__lineage-col { display: flex; flex-direction: column; gap: var(--vip-sp-4); min-width: 170px; }
.dd__lineage-head { font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); }
.dd__lineage-node { display: flex; align-items: center; gap: var(--vip-sp-3); padding: var(--vip-sp-4) var(--vip-sp-5); background: var(--vip-surface-2); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-md); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
.dd__lineage-node.is-current { border-color: var(--vip-brand-500); background: var(--vip-brand-soft); color: var(--vip-brand-text); font-weight: var(--vip-fw-medium); }
.dd__lineage-arrow { align-self: center; color: var(--vip-text-disabled); }

.dd__versions { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.dd__version { display: flex; align-items: center; gap: var(--vip-sp-5); padding: var(--vip-sp-4) 0; border-bottom: 1px solid var(--vip-border-subtle); }
.dd__version-body { display: flex; flex-direction: column; gap: 1px; }
.dd__version-note { font-size: var(--vip-fs-md); color: var(--vip-text-primary); }
.dd__version-meta { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }

.dd__feed { list-style: none; margin: 0 0 var(--vip-sp-5); padding: 0; }
.dd__feed-item { display: flex; gap: var(--vip-sp-4); padding: var(--vip-sp-4) 0; }
.dd__feed-dot { width: 26px; height: 26px; flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--vip-surface-3); color: var(--vip-text-muted); }
.dd__feed-body { display: flex; flex-direction: column; gap: 2px; }
.dd__feed-text { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
.dd__feed-time { font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); }

@media (max-width: 860px) { .dd__cards { grid-template-columns: 1fr 1fr; } .dd__profile-row { grid-template-columns: 1fr; } .dd__profile-range { text-align: left; } }
</style>
