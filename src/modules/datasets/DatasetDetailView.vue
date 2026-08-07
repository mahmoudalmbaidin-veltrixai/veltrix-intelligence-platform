<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { relativeTime, formatDateTime, formatNumber } from '@/shared/lib/format'
import { resourceCan } from '@/shared/lib/resourceAccess'
import { ApiError } from '@/shared/types/api'
import { useUiStore } from '@/shared/stores/ui'
import {
  datasetService,
  type Dataset,
  type DatasetActivityItem,
  type DatasetField,
  type DatasetVersion,
  type QualityRule,
  type QualityRuleStatus,
} from './datasets.service'
import { accessService, type ResourceEntry } from '@/modules/access/access.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'
import ResourceShareButton from '@/modules/access/ResourceShareButton.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const id = computed(() => String(route.params.id))

const {
  data: dataset,
  isLoading,
  refetch: refetchDataset,
} = useQuery(
  () => `dataset:${id.value}`,
  () => datasetService.get(id.value),
)
const { data: schema } = useQuery(
  () => `dataset:${id.value}:fields`,
  () => datasetService.listFields(id.value),
)
const previewPage = ref(1)
const effectiveAccessEarly = computed(() => dataset.value?.access)
const canQueryEarly = computed(() => resourceCan(effectiveAccessEarly.value, 'query'))
const {
  data: preview,
  isLoading: previewLoading,
  error: previewError,
} = useQuery(
  () => `dataset:${id.value}:preview:${previewPage.value}`,
  () => datasetService.preview(id.value, previewPage.value, 25),
  { enabled: canQueryEarly },
)
const { data: profile, isLoading: profileLoading } = useQuery(
  () => `dataset:${id.value}:profile`,
  () => datasetService.profile(id.value),
  { enabled: canQueryEarly },
)
const {
  data: lineage,
  isLoading: lineageLoading,
  error: lineageError,
} = useQuery(
  () => `dataset:${id.value}:lineage`,
  () => datasetService.getLineage(id.value),
)
const { data: rules } = useQuery(
  () => `dataset:${id.value}:quality-rules`,
  () => datasetService.listQualityRulesForDataset(id.value),
)

const accessEntries = ref<ResourceEntry[]>([])
const accessLoading = ref(false)
const accessError = ref<string | null>(null)
const activityItems = ref<DatasetActivityItem[]>([])
const activityLoading = ref(false)
const activityError = ref<string | null>(null)
const activityTotal = ref(0)
const versionItems = ref<DatasetVersion[]>([])
const versionsLoading = ref(false)
const versionsError = ref<string | null>(null)
const restoreBusy = ref<string | null>(null)
const certBusy = ref(false)
const certNote = ref('')

const datasetRules = computed<QualityRule[]>(() => rules.value ?? [])

const effectiveAccess = effectiveAccessEarly
const canManageAccess = computed(() => effectiveAccess.value?.canManageAccess ?? false)
const canQuery = canQueryEarly
const canCertify = computed(() => resourceCan(effectiveAccess.value, 'certify'))
const canEdit = computed(() => resourceCan(effectiveAccess.value, 'edit'))

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

async function loadAccess() {
  accessLoading.value = true
  accessError.value = null
  try {
    accessEntries.value = await accessService.listResourceAccess('dataset', id.value)
  } catch (error) {
    accessError.value = error instanceof ApiError ? error.message : 'Unable to load access grants.'
    accessEntries.value = []
  } finally {
    accessLoading.value = false
  }
}

async function loadActivity() {
  if (!datasetService.getActivity) {
    activityError.value = 'Activity is unavailable.'
    return
  }
  activityLoading.value = true
  activityError.value = null
  try {
    const page = await datasetService.getActivity(id.value, { limit: 50, offset: 0 })
    activityItems.value = page.items
    activityTotal.value = page.total
  } catch (error) {
    activityError.value = error instanceof ApiError ? error.message : 'Unable to load activity.'
    activityItems.value = []
  } finally {
    activityLoading.value = false
  }
}

async function loadVersions() {
  if (!datasetService.listVersions) {
    versionsError.value = 'Version history is unavailable.'
    return
  }
  versionsLoading.value = true
  versionsError.value = null
  try {
    versionItems.value = await datasetService.listVersions(id.value)
  } catch (error) {
    versionsError.value = error instanceof ApiError ? error.message : 'Unable to load versions.'
    versionItems.value = []
  } finally {
    versionsLoading.value = false
  }
}

async function restoreVersion(version: DatasetVersion) {
  if (!datasetService.restoreVersion || !dataset.value?.version || !canEdit.value) return
  restoreBusy.value = version.id
  try {
    await datasetService.restoreVersion(id.value, version.id, dataset.value.version)
    await refetchDataset()
    await loadVersions()
    ui.pushToast({
      kind: 'success',
      title: 'Version restored',
      message: `Restored version ${version.versionNumber}.`,
    })
  } catch (error) {
    ui.pushToast({
      kind: 'error',
      title: 'Restore failed',
      message: error instanceof ApiError ? error.message : 'Unable to restore this version.',
    })
  } finally {
    restoreBusy.value = null
  }
}

watch(activeTab, (tab) => {
  if (tab === 'access') void loadAccess()
  if (tab === 'activity') void loadActivity()
  if (tab === 'versions') void loadVersions()
})

async function certifyDataset() {
  if (!dataset.value?.version || !datasetService.certify || !canCertify.value) return
  certBusy.value = true
  try {
    await datasetService.certify(id.value, dataset.value.version, certNote.value.trim() || undefined)
    certNote.value = ''
    await refetchDataset()
    ui.pushToast({ kind: 'success', title: 'Certified', message: 'Dataset certification saved.' })
  } catch (error) {
    ui.pushToast({
      kind: 'error',
      title: 'Certification failed',
      message: error instanceof ApiError ? error.message : 'Unable to certify this dataset.',
    })
  } finally {
    certBusy.value = false
  }
}

async function revokeCertification() {
  if (!dataset.value?.version || !datasetService.revokeCertification || !canCertify.value) return
  certBusy.value = true
  try {
    await datasetService.revokeCertification(id.value, dataset.value.version, certNote.value.trim() || undefined)
    certNote.value = ''
    await refetchDataset()
    ui.pushToast({ kind: 'success', title: 'Revoked', message: 'Dataset certification revoked.' })
  } catch (error) {
    ui.pushToast({
      kind: 'error',
      title: 'Revoke failed',
      message: error instanceof ApiError ? error.message : 'Unable to revoke certification.',
    })
  } finally {
    certBusy.value = false
  }
}

const lineageUpstream = computed(() => {
  const graph = lineage.value
  const current = id.value
  if (!graph) return []
  const upstreamIds = new Set(graph.edges.filter((e) => e.to === current).map((e) => e.from))
  return graph.nodes.filter((n) => upstreamIds.has(n.id))
})
const lineageDownstream = computed(() => {
  const graph = lineage.value
  const current = id.value
  if (!graph) return []
  const downstreamIds = new Set(graph.edges.filter((e) => e.from === current).map((e) => e.to))
  return graph.nodes.filter((n) => downstreamIds.has(n.id))
})

function qualityTone(score: number | null): 'success' | 'warning' | 'danger' {
  if (score == null) return 'warning'
  if (score >= 90) return 'success'
  if (score >= 75) return 'warning'
  return 'danger'
}
const RULE_TONE: Record<QualityRuleStatus, 'success' | 'warning' | 'danger'> = {
  passing: 'success',
  warning: 'warning',
  failing: 'danger',
  unknown: 'warning',
  not_evaluated: 'warning',
}

function overviewCards(d: Dataset): { label: string; value: string; icon: string }[] {
  return [
    { label: 'Owner', value: d.owner, icon: 'users' },
    { label: 'Rows', value: formatNumber(d.rowCount, { style: 'compact' }), icon: 'hash' },
    { label: 'Quality score', value: d.qualityScore == null ? 'Not evaluated' : `${d.qualityScore}`, icon: 'gauge' },
    { label: 'Freshness', value: relativeTime(d.freshness), icon: 'clock' },
    { label: 'Source', value: d.source, icon: 'plug' },
    { label: 'Certification', value: d.certified ? 'Certified' : 'Uncertified', icon: 'shield' },
  ]
}

const schemaColumns: Column<DatasetField>[] = [
  { key: 'name', label: 'Column' },
  { key: 'type', label: 'Type' },
  { key: 'nullable', label: 'Nullable' },
  { key: 'description', label: 'Description' },
]

const previewColumns = computed<Column<Record<string, unknown>>[]>(() =>
  (preview.value?.columns ?? []).map((column) => ({
    key: column.name,
    label: column.displayName,
    cell: (row) => String(row[column.name] ?? '—'),
  })),
)

const accessColumns: Column<ResourceEntry>[] = [
  { key: 'subject_label', label: 'Principal' },
  { key: 'subject_type', label: 'Type' },
  { key: 'access_level', label: 'Level' },
  { key: 'effect', label: 'Effect' },
  { key: 'expires_at', label: 'Expires' },
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
          <VipBadge
            :tone="dataset.status === 'active' ? 'success' : dataset.status === 'building' ? 'info' : 'neutral'"
            variant="soft"
          >
            {{ dataset.status }}
          </VipBadge>
          <VipBadge v-if="dataset.certified" tone="brand" variant="soft">Certified</VipBadge>
          <VipBadge v-if="dataset.sensitive" tone="warning" variant="soft">Sensitive</VipBadge>
        </template>
        <template #actions>
          <VipButton variant="tertiary" icon="chevronLeft" @click="router.push('/datasets')">Back</VipButton>
          <VipButton variant="secondary" icon="lineage" @click="router.push('/datasets/lineage')"
            >View lineage</VipButton
          >
          <ResourceShareButton
            v-if="canManageAccess"
            resource-type="dataset"
            :resource-id="id"
            :resource-name="dataset.name"
            variant="secondary"
          />
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
        <VipCard class="dd__cert">
          <h3 class="dd__card-title">Certification</h3>
          <div class="dd__cert-facts">
            <div>
              <span>Status</span
              ><strong>{{ dataset.certificationStatus ?? (dataset.certified ? 'certified' : 'uncertified') }}</strong>
            </div>
            <div>
              <span>Certified by</span>
              <strong>{{ dataset.certifiedByUserId ?? '—' }}</strong>
            </div>
            <div>
              <span>Certified at</span>
              <strong>{{ dataset.certifiedAt ? formatDateTime(dataset.certifiedAt) : '—' }}</strong>
            </div>
            <div>
              <span>Note</span>
              <strong>{{ dataset.certificationNote || '—' }}</strong>
            </div>
          </div>
          <label v-if="canCertify" class="dd__cert-note">
            Note
            <input v-model="certNote" type="text" maxlength="2000" placeholder="Optional certification note" />
          </label>
          <div class="dd__cert-actions">
            <VipButton
              v-if="canCertify && !dataset.certified"
              variant="primary"
              size="sm"
              icon="shield"
              :loading="certBusy"
              @click="certifyDataset"
              >Certify</VipButton
            >
            <VipButton
              v-else-if="canCertify && dataset.certified"
              variant="danger"
              size="sm"
              icon="close"
              :loading="certBusy"
              @click="revokeCertification"
              >Revoke certification</VipButton
            >
            <p v-else class="dd__muted">
              {{
                canEdit
                  ? 'Edit access does not include certification. Certify capability is required.'
                  : 'Certification requires the certify capability on this dataset.'
              }}
            </p>
          </div>
        </VipCard>
        <VipCard class="dd__tags-card">
          <h3 class="dd__card-title">Tags</h3>
          <div class="dd__tags">
            <VipBadge v-for="t in dataset.tags" :key="t" tone="neutral" variant="soft" size="sm">{{ t }}</VipBadge>
          </div>
        </VipCard>
      </section>

      <!-- DATA PREVIEW -->
      <VipCard v-else-if="activeTab === 'preview'" :padded="false">
        <VipEmptyState
          v-if="!canQuery"
          icon="warning"
          tone="warning"
          title="Preview not permitted"
          description="Query access on this dataset is required to view preview rows. Frontend visibility is not the security boundary — the API enforces this independently."
        />
        <template v-else>
          <div class="dd__preview-head">
            <span class="dd__mono">{{ dataset.name }} · page {{ previewPage }}</span>
            <VipBadge v-if="preview?.maskedFields.length" tone="warning" variant="soft" size="sm">
              sensitive values masked
            </VipBadge>
          </div>
          <div v-if="previewLoading" class="dd__loading"><VipSpinner label="Loading live preview…" /></div>
          <VipEmptyState
            v-else-if="previewError"
            icon="warning"
            tone="warning"
            title="Preview failed"
            :description="String(previewError)"
          />
          <VipTable
            v-else-if="preview?.rows.length"
            :columns="previewColumns"
            :rows="preview.rows"
            :row-key="(row) => JSON.stringify(row)"
            density="compact"
          />
          <VipEmptyState
            v-else
            icon="table"
            title="No preview rows"
            description="The source returned no rows for this page."
          />
          <div class="dd__pager">
            <VipButton size="sm" :disabled="previewPage === 1" @click="previewPage--">Previous</VipButton>
            <VipButton
              size="sm"
              :disabled="(preview?.returnedRows ?? 0) < (preview?.pageSize ?? 25)"
              @click="previewPage++"
              >Next</VipButton
            >
          </div>
        </template>
      </VipCard>

      <!-- SCHEMA -->
      <VipCard v-else-if="activeTab === 'schema'" :padded="false">
        <VipTable :columns="schemaColumns" :rows="schema ?? []" :row-key="(r) => r.name" density="compact">
          <template #cell-name="{ row }"
            ><span class="dd__mono">{{ row.name }}</span></template
          >
          <template #cell-type="{ row }"
            ><span class="dd__mono">{{ row.type }}</span></template
          >
          <template #cell-nullable="{ row }">
            <VipBadge :tone="row.nullable ? 'neutral' : 'success'" variant="soft" size="sm">{{
              row.nullable ? 'nullable' : 'not null'
            }}</VipBadge>
          </template>
        </VipTable>
      </VipCard>

      <!-- PROFILE -->
      <VipCard v-else-if="activeTab === 'profile'">
        <VipEmptyState
          v-if="!canQuery"
          icon="warning"
          tone="warning"
          title="Profile not permitted"
          description="Query access on this dataset is required to view column profiles."
        />
        <template v-else>
          <h3 class="dd__card-title">Column profile</h3>
          <p class="dd__muted">Live statistics over {{ profile?.sampleSize ?? 0 }} sampled rows.</p>
          <div v-if="profileLoading" class="dd__loading"><VipSpinner label="Profiling dataset…" /></div>
          <ul v-else-if="profile?.fields.length" class="dd__profile">
            <li v-for="p in profile.fields" :key="p.name" class="dd__profile-row">
              <span class="dd__profile-name">{{ p.name }}</span>
              <div class="dd__profile-bars">
                <div class="dd__bar-group">
                  <span class="dd__bar-label">nulls {{ p.nullCount }}</span>
                  <div class="dd__bar-track">
                    <div
                      class="dd__bar dd__bar--null"
                      :style="{ width: `${profile.sampleSize ? (p.nullCount / profile.sampleSize) * 100 : 0}%` }"
                    />
                  </div>
                </div>
                <div class="dd__bar-group">
                  <span class="dd__bar-label">distinct {{ p.distinctCount }}</span>
                  <div class="dd__bar-track">
                    <div
                      class="dd__bar dd__bar--distinct"
                      :style="{ width: `${profile.sampleSize ? (p.distinctCount / profile.sampleSize) * 100 : 0}%` }"
                    />
                  </div>
                </div>
              </div>
              <span class="dd__profile-range">{{ p.minimum ?? '—' }} … {{ p.maximum ?? '—' }}</span>
            </li>
          </ul>
          <VipEmptyState
            v-else
            icon="gauge"
            title="No profile available"
            description="The source has no fields to profile."
          />
        </template>
      </VipCard>

      <!-- QUALITY -->
      <VipCard v-else-if="activeTab === 'quality'">
        <div class="dd__quality-head">
          <h3 class="dd__card-title">Quality rules</h3>
          <VipBadge :tone="qualityTone(dataset.qualityScore)" variant="soft">
            {{ dataset.qualityScore == null ? 'Not evaluated' : `Score ${dataset.qualityScore}` }}
          </VipBadge>
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
          <template #cell-dimension="{ row }"
            ><VipBadge tone="neutral" variant="soft" size="sm">{{ row.dimension }}</VipBadge></template
          >
          <template #cell-severity="{ row }">
            <VipBadge
              :tone="row.severity === 'high' ? 'danger' : row.severity === 'medium' ? 'warning' : 'neutral'"
              variant="soft"
              size="sm"
              >{{ row.severity }}</VipBadge
            >
          </template>
          <template #cell-status="{ row }"
            ><VipBadge :tone="RULE_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge></template
          >
          <template #cell-passRate="{ row }">{{ row.passRate }}%</template>
        </VipTable>
        <VipEmptyState
          v-else
          icon="gauge"
          title="No rules on this dataset"
          description="Attach quality rules from the Data Quality workspace."
        />
      </VipCard>

      <!-- LINEAGE -->
      <VipCard v-else-if="activeTab === 'lineage'">
        <h3 class="dd__card-title">Lineage</h3>
        <div v-if="lineageLoading" class="dd__loading"><VipSpinner label="Loading lineage…" /></div>
        <VipEmptyState
          v-else-if="lineageError"
          icon="warning"
          tone="warning"
          title="Unable to load lineage"
          :description="String(lineageError)"
        />
        <template v-else>
          <div class="dd__lineage">
            <div class="dd__lineage-col">
              <span class="dd__lineage-head">Upstream</span>
              <div v-if="!lineageUpstream.length" class="dd__muted">No upstream resources</div>
              <div v-for="n in lineageUpstream" :key="n.id" class="dd__lineage-node">
                <VipIcon name="database" :size="14" />{{ n.name }}
              </div>
            </div>
            <VipIcon name="chevronRight" :size="18" class="dd__lineage-arrow" />
            <div class="dd__lineage-col">
              <span class="dd__lineage-head">This dataset</span>
              <div class="dd__lineage-node is-current"><VipIcon name="database" :size="14" />{{ dataset.name }}</div>
            </div>
            <VipIcon name="chevronRight" :size="18" class="dd__lineage-arrow" />
            <div class="dd__lineage-col">
              <span class="dd__lineage-head">Downstream</span>
              <div v-if="!lineageDownstream.length" class="dd__muted">No downstream resources</div>
              <div v-for="n in lineageDownstream" :key="n.id" class="dd__lineage-node">
                <VipIcon name="database" :size="14" />{{ n.name }}
              </div>
            </div>
          </div>
          <VipButton variant="tertiary" icon="lineage" @click="router.push('/datasets/lineage')"
            >Open full lineage graph</VipButton
          >
        </template>
      </VipCard>

      <!-- ACCESS -->
      <VipCard v-else-if="activeTab === 'access'" :padded="false">
        <div v-if="accessLoading" class="dd__loading"><VipSpinner label="Loading access…" /></div>
        <VipEmptyState
          v-else-if="accessError"
          icon="warning"
          tone="warning"
          title="Unable to load access"
          :description="accessError"
        />
        <VipEmptyState
          v-else-if="!accessEntries.length"
          icon="users"
          title="No direct access grants"
          description="This dataset may still be reachable via ownership or workspace roles. Use Share to grant resource ACL access when authorized."
        />
        <VipTable v-else :columns="accessColumns" :rows="accessEntries" :row-key="(r) => r.id" density="compact">
          <template #cell-access_level="{ row }"
            ><VipBadge tone="brand" variant="soft" size="sm">{{ row.access_level }}</VipBadge></template
          >
          <template #cell-effect="{ row }"
            ><VipBadge :tone="row.effect === 'deny' ? 'danger' : 'success'" variant="soft" size="sm">{{
              row.effect
            }}</VipBadge></template
          >
          <template #cell-expires_at="{ row }">{{
            row.expires_at ? formatDateTime(row.expires_at) : 'Never'
          }}</template>
        </VipTable>
      </VipCard>

      <!-- VERSIONS — no history API exists -->
      <VipCard v-else-if="activeTab === 'versions'">
        <h3 class="dd__card-title">Version history</h3>
        <div v-if="versionsLoading" class="dd__loading"><VipSpinner label="Loading versions…" /></div>
        <VipEmptyState
          v-else-if="versionsError"
          icon="alertTriangle"
          title="Versions unavailable"
          :description="versionsError"
        >
          <VipButton variant="secondary" size="sm" icon="refresh" @click="loadVersions">Retry</VipButton>
        </VipEmptyState>
        <VipEmptyState
          v-else-if="versionItems.length === 0"
          icon="clock"
          title="No versions yet"
          description="Versions are captured when a dataset is registered, certified or restored."
        />
        <ul v-else class="dd__versions">
          <li v-for="v in versionItems" :key="v.id" class="dd__version">
            <div>
              <div class="dd__version-meta">
                <VipBadge tone="neutral" variant="soft" size="sm">v{{ v.versionNumber }}</VipBadge>
                <VipBadge tone="info" variant="soft" size="sm">{{ v.versionType }}</VipBadge>
                <span class="dd__muted">{{ new Date(v.createdAt).toLocaleString() }}</span>
              </div>
              <p class="dd__version-note">{{ v.changeSummary || '—' }}</p>
            </div>
            <VipButton
              v-if="canEdit"
              variant="secondary"
              size="sm"
              icon="history"
              :loading="restoreBusy === v.id"
              :disabled="restoreBusy !== null"
              @click="restoreVersion(v)"
            >
              Restore
            </VipButton>
          </li>
        </ul>
      </VipCard>

      <!-- ACTIVITY -->
      <VipCard v-else>
        <h3 class="dd__card-title">Recent activity</h3>
        <div v-if="activityLoading" class="dd__loading"><VipSpinner label="Loading activity…" /></div>
        <VipEmptyState
          v-else-if="activityError"
          icon="warning"
          tone="warning"
          title="Unable to load activity"
          :description="activityError"
        />
        <VipEmptyState
          v-else-if="!activityItems.length"
          icon="clock"
          title="No activity yet"
          description="Audit events for this dataset will appear here after create, update, certify, quality, and access actions."
        />
        <ul v-else class="dd__feed">
          <li v-for="a in activityItems" :key="a.id" class="dd__feed-item">
            <span class="dd__feed-dot"><VipIcon name="shield" :size="13" /></span>
            <div class="dd__feed-body">
              <span class="dd__feed-text"
                ><strong>{{ a.actorUserId ?? 'system' }}</strong> {{ a.eventType }}
                <VipBadge tone="neutral" variant="soft" size="sm">{{ a.outcome }}</VipBadge></span
              >
              <span class="dd__feed-time">{{ relativeTime(a.occurredAt) }} · {{ formatDateTime(a.occurredAt) }}</span>
            </div>
          </li>
        </ul>
        <p v-if="activityTotal" class="dd__muted">{{ activityTotal }} event(s) total</p>
      </VipCard>
    </template>
  </div>
</template>

<style scoped>
.dd {
  max-width: 1200px;
  margin: 0 auto;
}
.dd__loading {
  display: flex;
  justify-content: center;
  padding: var(--vip-sp-12);
}
.dd__card-title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-5);
}
.dd__muted {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.dd__cert {
  margin-bottom: var(--vip-sp-5);
}
.dd__cert-facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-5);
  font-size: var(--vip-fs-sm);
}
.dd__cert-facts span {
  display: block;
  color: var(--vip-text-muted);
  margin-bottom: 2px;
}
.dd__cert-note {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  margin-bottom: var(--vip-sp-4);
}
.dd__cert-note input {
  height: 34px;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  padding: 0 var(--vip-sp-4);
  background: var(--vip-surface-2);
  color: var(--vip-text-primary);
}
.dd__cert-actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  flex-wrap: wrap;
}
.dd__mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}

.dd__cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--vip-sp-6);
}
.dd__stat {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.dd__stat-icon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.dd__stat-value {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  margin-top: var(--vip-sp-3);
}
.dd__stat-label {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.dd__tags-card {
  margin-top: var(--vip-sp-6);
}
.dd__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3);
}

.dd__preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.dd__pager {
  display: flex;
  justify-content: flex-end;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-4) var(--vip-sp-6);
  border-top: 1px solid var(--vip-border-subtle);
}

.dd__profile {
  list-style: none;
  margin: var(--vip-sp-5) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.dd__profile-row {
  display: grid;
  grid-template-columns: 160px 1fr 200px;
  align-items: center;
  gap: var(--vip-sp-6);
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.dd__profile-name {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
}
.dd__profile-bars {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.dd__bar-group {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.dd__bar-label {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
  width: 88px;
  flex: none;
}
.dd__bar-track {
  flex: 1;
  height: 6px;
  background: var(--vip-surface-3);
  border-radius: var(--vip-radius-full);
  overflow: hidden;
}
.dd__bar {
  height: 100%;
  border-radius: var(--vip-radius-full);
}
.dd__bar--null {
  background: var(--vip-warning);
}
.dd__bar--distinct {
  background: var(--vip-brand-500);
}
.dd__profile-range {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  text-align: right;
}

.dd__quality-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--vip-sp-5);
}

.dd__lineage {
  display: flex;
  align-items: stretch;
  gap: var(--vip-sp-6);
  margin-bottom: var(--vip-sp-6);
  overflow-x: auto;
}
.dd__lineage-col {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
  min-width: 170px;
}
.dd__lineage-head {
  font-size: var(--vip-fs-xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
}
.dd__lineage-node {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.dd__lineage-node.is-current {
  border-color: var(--vip-brand-500);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  font-weight: var(--vip-fw-medium);
}
.dd__lineage-arrow {
  align-self: center;
  color: var(--vip-text-disabled);
}

.dd__versions {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.dd__version {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.dd__version-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.dd__version-note {
  font-size: var(--vip-fs-md);
  color: var(--vip-text-primary);
}
.dd__version-meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}

.dd__feed {
  list-style: none;
  margin: 0 0 var(--vip-sp-5);
  padding: 0;
}
.dd__feed-item {
  display: flex;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) 0;
}
.dd__feed-dot {
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
.dd__feed-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dd__feed-text {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.dd__feed-time {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
}

@media (max-width: 860px) {
  .dd__cards {
    grid-template-columns: 1fr 1fr;
  }
  .dd__profile-row {
    grid-template-columns: 1fr;
  }
  .dd__profile-range {
    text-align: left;
  }
}
</style>
