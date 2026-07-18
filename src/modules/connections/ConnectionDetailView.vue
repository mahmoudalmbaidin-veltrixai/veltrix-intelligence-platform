<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime, formatDateTime, formatDuration, formatNumber } from '@/shared/lib/format'
import {
  connectionService,
  CONNECTOR_ICON,
  CONNECTOR_LABEL,
  type Connection,
  type ConnectionStatus,
  type ConnectionTestResult,
} from './connections.service'
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
const ui = useUiStore()
const id = computed(() => String(route.params.id))

const { data: connection, isLoading } = useQuery(
  () => `connection:${id.value}`,
  () => connectionService.get(id.value),
)

const STATUS_TONE: Record<ConnectionStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  healthy: 'success',
  degraded: 'warning',
  error: 'danger',
  configuring: 'info',
}
const STATUS_LABEL: Record<ConnectionStatus, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  error: 'Error',
  configuring: 'Configuring',
}

const tabs = [
  { value: 'overview', label: 'Overview' },
  { value: 'configuration', label: 'Configuration' },
  { value: 'schema', label: 'Schema' },
  { value: 'preview', label: 'Preview' },
  { value: 'health', label: 'Health' },
  { value: 'dependencies', label: 'Dependencies' },
  { value: 'activity', label: 'Activity' },
  { value: 'audit', label: 'Audit' },
]
const activeTab = ref('overview')

/* ---- live-ish test button ---- */
const testing = ref(false)
const lastTest = ref<ConnectionTestResult | undefined>(undefined)
async function runTest() {
  testing.value = true
  lastTest.value = await connectionService.test(id.value)
  testing.value = false
  ui.pushToast({
    kind: lastTest.value.ok ? 'success' : 'error',
    title: lastTest.value.ok ? 'Connection healthy' : 'Connection test failed',
    message: lastTest.value.message,
  })
}

/* ---- derived mock content ---- */
function facts(c: Connection): { label: string; value: string; mono?: boolean }[] {
  return [
    { label: 'Connector', value: CONNECTOR_LABEL[c.connector] },
    { label: 'Owner', value: c.owner },
    { label: 'Host / endpoint', value: c.host ?? '—', mono: true },
    { label: 'Created', value: formatDateTime(c.createdAt) },
    { label: 'Last tested', value: relativeTime(c.lastTested) },
    { label: 'Connection ID', value: c.id, mono: true },
  ]
}

interface SchemaRow {
  table: string
  columns: number
  rows: number
  type: string
}
const schemaRows: SchemaRow[] = [
  { table: 'public.orders', columns: 14, rows: 1_284_502, type: 'table' },
  { table: 'public.customers', columns: 22, rows: 84_213, type: 'table' },
  { table: 'public.invoices', columns: 18, rows: 902_144, type: 'table' },
  { table: 'public.products', columns: 11, rows: 12_408, type: 'table' },
  { table: 'analytics.daily_revenue', columns: 6, rows: 3_650, type: 'view' },
]
const schemaColumns: Column<SchemaRow>[] = [
  { key: 'table', label: 'Object' },
  { key: 'type', label: 'Type' },
  { key: 'columns', label: 'Columns', align: 'right' },
  { key: 'rows', label: 'Rows', align: 'right' },
]

interface PreviewRow {
  id: number
  customer: string
  amount: number
  status: string
  placed: string
}
const previewRows: PreviewRow[] = [
  { id: 90211, customer: 'Northwind Trading', amount: 12480, status: 'paid', placed: '2026-07-14' },
  { id: 90210, customer: 'Cedar & Co', amount: 3120, status: 'pending', placed: '2026-07-14' },
  { id: 90209, customer: 'Atlas Robotics', amount: 58900, status: 'paid', placed: '2026-07-13' },
  { id: 90208, customer: 'Bluewave Media', amount: 740, status: 'refunded', placed: '2026-07-13' },
  { id: 90207, customer: 'Meridian Health', amount: 22150, status: 'paid', placed: '2026-07-12' },
]
const previewColumns: Column<PreviewRow>[] = [
  { key: 'id', label: 'order_id', align: 'right' },
  { key: 'customer', label: 'customer' },
  {
    key: 'amount',
    label: 'amount',
    align: 'right',
    cell: (r) => formatNumber(r.amount, { style: 'currency', currency: 'USD', decimals: 0 }),
  },
  { key: 'status', label: 'status' },
  { key: 'placed', label: 'placed_at' },
]

const latencySeries = [62, 58, 71, 66, 59, 84, 78, 61, 57, 63, 69, 74]
const maxLatency = Math.max(...latencySeries)

interface Dependency {
  name: string
  type: string
  icon: string
}
const dependencies: Dependency[] = [
  { name: 'Revenue Nightly ETL', type: 'Pipeline', icon: 'workflow' },
  { name: 'fct_orders', type: 'Dataset', icon: 'database' },
  { name: 'Sales Analytics', type: 'Semantic Model', icon: 'layers' },
  { name: 'Executive Overview', type: 'Dashboard', icon: 'chart' },
]

interface ActivityItem {
  id: string
  actor: string
  action: string
  when: string
  icon: string
}
const activity: ActivityItem[] = [
  { id: 'e1', actor: 'Nightly Scheduler', action: 'ran a scheduled sync', when: '18m', icon: 'run' },
  { id: 'e2', actor: 'M. Almbaidin', action: 'tested the connection', when: '2h', icon: 'play' },
  { id: 'e3', actor: 'System', action: 'rotated credentials', when: '3d', icon: 'key' },
  { id: 'e4', actor: 'A. Rahman', action: 'updated connection settings', when: '6d', icon: 'settings' },
]

interface AuditItem {
  id: string
  event: string
  actor: string
  ip: string
  when: string
}
const audit: AuditItem[] = [
  { id: 'a1', event: 'connection.tested', actor: 'mahmoud.almbaidin', ip: '10.4.2.11', when: '2h ago' },
  { id: 'a2', event: 'connection.updated', actor: 'a.rahman', ip: '10.4.2.30', when: '6d ago' },
  { id: 'a3', event: 'connection.created', actor: 'system', ip: '—', when: '210d ago' },
]
const auditColumns: Column<AuditItem>[] = [
  { key: 'event', label: 'Event' },
  { key: 'actor', label: 'Actor' },
  { key: 'ip', label: 'IP address' },
  { key: 'when', label: 'When', align: 'right' },
]
</script>

<template>
  <div class="cd">
    <div v-if="isLoading" class="cd__loading"><VipSpinner label="Loading connection…" /></div>

    <VipEmptyState
      v-else-if="!connection"
      icon="warning"
      tone="warning"
      title="Connection not found"
      description="This connection may have been deleted or you may not have access."
    >
      <VipButton variant="primary" @click="router.push('/connections')">Back to connections</VipButton>
    </VipEmptyState>

    <template v-else>
      <VipPageHeader :title="connection.name">
        <template #status>
          <VipBadge :tone="STATUS_TONE[connection.status]" variant="soft" size="md">
            {{ STATUS_LABEL[connection.status] }}
          </VipBadge>
          <span class="cd__connector">
            <VipIcon :name="CONNECTOR_ICON[connection.connector]" :size="14" />
            {{ CONNECTOR_LABEL[connection.connector] }}
          </span>
        </template>
        <template #actions>
          <VipButton variant="tertiary" icon="chevronLeft" @click="router.push('/connections')">Back</VipButton>
          <VipButton variant="primary" icon="play" :loading="testing" @click="runTest">Test connection</VipButton>
        </template>
        <template #tabs>
          <VipTabs v-model="activeTab" :tabs="tabs" />
        </template>
      </VipPageHeader>

      <!-- OVERVIEW -->
      <section v-if="activeTab === 'overview'" class="cd__grid">
        <VipCard>
          <h3 class="cd__card-title">Connection facts</h3>
          <dl class="cd__facts">
            <div v-for="f in facts(connection)" :key="f.label" class="cd__fact">
              <dt>{{ f.label }}</dt>
              <dd :class="{ 'is-mono': f.mono }">{{ f.value }}</dd>
            </div>
          </dl>
        </VipCard>
        <VipCard>
          <h3 class="cd__card-title">Latest test</h3>
          <div v-if="lastTest" class="cd__test" :class="lastTest.ok ? 'is-ok' : 'is-fail'">
            <VipIcon :name="lastTest.ok ? 'success' : 'error'" :size="18" />
            <div>
              <div class="cd__test-title">
                {{ lastTest.ok ? 'Healthy' : 'Failed' }} · {{ formatDuration(lastTest.latencyMs) }}
              </div>
              <p class="cd__test-msg">{{ lastTest.message }}</p>
            </div>
          </div>
          <p v-else class="cd__muted">Run a test to see current connectivity and latency.</p>
        </VipCard>
      </section>

      <!-- CONFIGURATION -->
      <VipCard v-else-if="activeTab === 'configuration'">
        <h3 class="cd__card-title">Configuration</h3>
        <dl class="cd__facts cd__facts--wide">
          <div class="cd__fact">
            <dt>Connector type</dt>
            <dd>{{ CONNECTOR_LABEL[connection.connector] }}</dd>
          </div>
          <div class="cd__fact">
            <dt>Endpoint</dt>
            <dd class="is-mono">{{ connection.host ?? '—' }}</dd>
          </div>
          <div class="cd__fact">
            <dt>Owner</dt>
            <dd>{{ connection.owner }}</dd>
          </div>
          <div class="cd__fact">
            <dt>SSL / TLS</dt>
            <dd>Enabled (verify-full)</dd>
          </div>
          <div class="cd__fact">
            <dt>Pool size</dt>
            <dd>10 connections</dd>
          </div>
          <div class="cd__fact">
            <dt>Read replica</dt>
            <dd>Preferred</dd>
          </div>
        </dl>
      </VipCard>

      <!-- SCHEMA -->
      <VipCard v-else-if="activeTab === 'schema'" :padded="false">
        <VipTable :columns="schemaColumns" :rows="schemaRows" :row-key="(r) => r.table" density="compact">
          <template #cell-table="{ row }"
            ><span class="cd__mono">{{ row.table }}</span></template
          >
          <template #cell-type="{ row }">
            <VipBadge :tone="row.type === 'view' ? 'info' : 'neutral'" variant="soft" size="sm">{{
              row.type
            }}</VipBadge>
          </template>
          <template #cell-columns="{ row }">{{ formatNumber(row.columns) }}</template>
          <template #cell-rows="{ row }">{{ formatNumber(row.rows, { style: 'compact' }) }}</template>
        </VipTable>
      </VipCard>

      <!-- PREVIEW -->
      <VipCard v-else-if="activeTab === 'preview'" :padded="false">
        <div class="cd__preview-head">
          <span class="cd__mono">SELECT * FROM public.orders LIMIT 5</span>
          <VipBadge tone="neutral" variant="soft" size="sm">sample</VipBadge>
        </div>
        <VipTable :columns="previewColumns" :rows="previewRows" :row-key="(r) => String(r.id)" density="compact">
          <template #cell-status="{ row }">
            <VipBadge
              :tone="row.status === 'paid' ? 'success' : row.status === 'refunded' ? 'danger' : 'warning'"
              variant="soft"
              size="sm"
              >{{ row.status }}</VipBadge
            >
          </template>
        </VipTable>
      </VipCard>

      <!-- HEALTH -->
      <section v-else-if="activeTab === 'health'" class="cd__grid">
        <VipCard>
          <h3 class="cd__card-title">Status</h3>
          <div class="cd__health-status">
            <VipBadge :tone="STATUS_TONE[connection.status]" variant="soft" size="md">{{
              STATUS_LABEL[connection.status]
            }}</VipBadge>
            <span class="cd__muted">Last checked {{ relativeTime(connection.lastTested) }}</span>
          </div>
          <div class="cd__stats">
            <div class="cd__stat">
              <span class="cd__stat-value">99.94%</span><span class="cd__stat-label">Uptime (30d)</span>
            </div>
            <div class="cd__stat">
              <span class="cd__stat-value">{{ formatDuration(66) }}</span
              ><span class="cd__stat-label">Avg latency</span>
            </div>
            <div class="cd__stat">
              <span class="cd__stat-value">1.2k</span><span class="cd__stat-label">Syncs (30d)</span>
            </div>
          </div>
        </VipCard>
        <VipCard>
          <h3 class="cd__card-title">Latency (last 12 checks)</h3>
          <div class="cd__spark">
            <div
              v-for="(v, i) in latencySeries"
              :key="i"
              class="cd__spark-bar"
              :style="{ height: `${(v / maxLatency) * 100}%` }"
              :title="`${v}ms`"
            />
          </div>
          <p class="cd__muted">Peak {{ maxLatency }}ms · steady response times over the sampling window.</p>
        </VipCard>
      </section>

      <!-- DEPENDENCIES -->
      <VipCard v-else-if="activeTab === 'dependencies'">
        <h3 class="cd__card-title">Downstream dependencies</h3>
        <p class="cd__muted">Resources that consume data from this connection.</p>
        <ul class="cd__deps">
          <li v-for="d in dependencies" :key="d.name" class="cd__dep">
            <span class="cd__dep-icon"><VipIcon :name="d.icon" :size="16" /></span>
            <span class="cd__dep-name">{{ d.name }}</span>
            <VipBadge tone="neutral" variant="soft" size="sm">{{ d.type }}</VipBadge>
          </li>
        </ul>
      </VipCard>

      <!-- ACTIVITY -->
      <VipCard v-else-if="activeTab === 'activity'">
        <h3 class="cd__card-title">Recent activity</h3>
        <ul class="cd__feed">
          <li v-for="a in activity" :key="a.id" class="cd__feed-item">
            <span class="cd__feed-dot"><VipIcon :name="a.icon" :size="13" /></span>
            <div class="cd__feed-body">
              <span class="cd__feed-text"
                ><strong>{{ a.actor }}</strong> {{ a.action }}</span
              >
              <span class="cd__feed-time">{{ a.when }} ago</span>
            </div>
          </li>
        </ul>
      </VipCard>

      <!-- AUDIT -->
      <VipCard v-else :padded="false">
        <VipTable :columns="auditColumns" :rows="audit" :row-key="(r) => r.id" density="compact">
          <template #cell-event="{ row }"
            ><span class="cd__mono">{{ row.event }}</span></template
          >
          <template #cell-ip="{ row }"
            ><span class="cd__mono">{{ row.ip }}</span></template
          >
        </VipTable>
      </VipCard>
    </template>
  </div>
</template>

<style scoped>
.cd {
  max-width: 1200px;
  margin: 0 auto;
}
.cd__loading {
  display: flex;
  justify-content: center;
  padding: var(--vip-sp-12);
}
.cd__connector {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}

.cd__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-6);
  align-items: start;
}
.cd__card-title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-5);
}

.cd__facts {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.cd__facts--wide {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--vip-sp-8);
}
.cd__fact {
  display: flex;
  justify-content: space-between;
  gap: var(--vip-sp-6);
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.cd__fact dt {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.cd__fact dd {
  font-size: var(--vip-fs-md);
  color: var(--vip-text-primary);
  font-weight: var(--vip-fw-medium);
  text-align: right;
}
.cd__fact dd.is-mono {
  font-family: var(--vip-font-mono);
  font-weight: var(--vip-fw-regular);
  font-size: var(--vip-fs-sm);
}

.cd__test {
  display: flex;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-5);
  border-radius: var(--vip-radius-md);
}
.cd__test.is-ok {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.cd__test.is-fail {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.cd__test-title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.cd__test-msg {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin-top: var(--vip-sp-2);
}
.cd__muted {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.cd__mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}

.cd__health-status {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
  margin-bottom: var(--vip-sp-6);
}
.cd__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--vip-sp-5);
}
.cd__stat {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  padding: var(--vip-sp-5);
  background: var(--vip-surface-2);
  border-radius: var(--vip-radius-md);
}
.cd__stat-value {
  font-size: var(--vip-fs-xl);
  font-weight: var(--vip-fw-bold);
  font-variant-numeric: tabular-nums;
}
.cd__stat-label {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}

.cd__spark {
  display: flex;
  align-items: flex-end;
  gap: var(--vip-sp-3);
  height: 96px;
  margin-bottom: var(--vip-sp-5);
}
.cd__spark-bar {
  flex: 1;
  background: var(--vip-brand-500);
  border-radius: var(--vip-radius-xs) var(--vip-radius-xs) 0 0;
  min-height: 4px;
}

.cd__preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
}

.cd__deps {
  list-style: none;
  margin: var(--vip-sp-5) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.cd__dep {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.cd__dep-icon {
  color: var(--vip-text-muted);
}
.cd__dep-name {
  flex: 1;
  font-size: var(--vip-fs-md);
  color: var(--vip-text-primary);
  font-weight: var(--vip-fw-medium);
}

.cd__feed {
  list-style: none;
  margin: 0;
  padding: 0;
}
.cd__feed-item {
  display: flex;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) 0;
}
.cd__feed-dot {
  width: 26px;
  height: 26px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--vip-surface-3);
  color: var(--vip-text-muted);
}
.cd__feed-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cd__feed-text {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.cd__feed-time {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
}

@media (max-width: 860px) {
  .cd__grid,
  .cd__facts--wide,
  .cd__stats {
    grid-template-columns: 1fr;
  }
}
</style>
