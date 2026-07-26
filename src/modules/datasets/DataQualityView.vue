<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useQuery, useMutation } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import {
  datasetService,
  type QualityRule,
  type QualityRuleStatus,
  type QualitySeverity,
  type QualityIncident,
  type IncidentStatus,
  type CreateRulePayload,
} from './datasets.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()

const { data: rules, isLoading: rulesLoading } = useQuery('quality:rules', () => datasetService.listQualityRules())
const { data: datasets } = useQuery('quality:datasets', () => datasetService.list())
const { data: incidents, isLoading: incidentsLoading } = useQuery('quality:incidents', () =>
  datasetService.listIncidents(),
)

/* ---- severity / status tone maps ---- */
const RULE_TONE: Record<QualityRuleStatus, 'success' | 'warning' | 'danger'> = {
  passing: 'success',
  warning: 'warning',
  failing: 'danger',
  unknown: 'warning',
  not_evaluated: 'warning',
}
function severityTone(s: QualitySeverity): 'danger' | 'warning' | 'neutral' {
  return s === 'high' ? 'danger' : s === 'medium' ? 'warning' : 'neutral'
}
const INCIDENT_TONE: Record<IncidentStatus, 'danger' | 'warning' | 'success'> = {
  open: 'danger',
  investigating: 'warning',
  resolved: 'success',
}

/* ---- rules table ---- */
const ruleColumns: Column<QualityRule>[] = [
  { key: 'name', label: 'Rule', width: '30%' },
  { key: 'dimension', label: 'Dimension' },
  { key: 'severity', label: 'Severity' },
  { key: 'status', label: 'Status' },
  { key: 'passRate', label: 'Pass rate', align: 'right' },
  { key: 'lastRun', label: 'Last run', align: 'right' },
]

/* ---- create rule dialog ---- */
const dialogOpen = ref(false)
interface RuleForm {
  datasetId: string
  fieldId: string
  name: string
  ruleType: CreateRulePayload['ruleType']
  severity: QualitySeverity
  minimum: number | null
  maximum: number | null
  values: string
  pattern: string
}
const ruleForm = reactive<RuleForm>({
  datasetId: '',
  fieldId: '',
  name: '',
  ruleType: 'not_null',
  severity: 'medium',
  minimum: null,
  maximum: null,
  values: '',
  pattern: '',
})
const formError = ref('')

const ruleTypeOptions: { value: string; label: string }[] = [
  { value: 'not_null', label: 'Not null' },
  { value: 'unique', label: 'Unique' },
  { value: 'accepted_values', label: 'Accepted values' },
  { value: 'range', label: 'Numeric range' },
  { value: 'regex', label: 'Regular expression' },
  { value: 'freshness', label: 'Freshness' },
  { value: 'row_count', label: 'Row count' },
]
const severityOptions: { value: string; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]
const datasetOptions = computed(() => (datasets.value ?? []).map((item) => ({ value: item.id, label: item.name })))
const historyDatasetId = computed(() => ruleForm.datasetId || datasetOptions.value[0]?.value || '')
const { data: history, isLoading: historyLoading } = useQuery(
  () => `quality:history:${historyDatasetId.value || 'none'}`,
  () => (historyDatasetId.value ? datasetService.qualityHistory(historyDatasetId.value) : Promise.resolve([])),
)
const { data: fields } = useQuery(
  () => `quality:fields:${ruleForm.datasetId || 'none'}`,
  () => (ruleForm.datasetId ? datasetService.listFields(ruleForm.datasetId) : Promise.resolve([])),
)
const fieldOptions = computed(() =>
  (fields.value ?? []).map((item) => ({ value: item.id ?? '', label: `${item.name} · ${item.type}` })),
)

function openDialog() {
  ruleForm.datasetId = datasetOptions.value[0]?.value ?? ''
  ruleForm.fieldId = ''
  ruleForm.name = ''
  ruleForm.ruleType = 'not_null'
  ruleForm.severity = 'medium'
  ruleForm.minimum = null
  ruleForm.maximum = null
  ruleForm.values = ''
  ruleForm.pattern = ''
  formError.value = ''
  dialogOpen.value = true
}

const createRule = useMutation<CreateRulePayload, QualityRule>((payload) => datasetService.createRule(payload), {
  invalidate: ['quality:rules'],
  onSuccess: (rule) => {
    ui.pushToast({ kind: 'success', title: 'Rule created', message: `“${rule.name}” is now monitoring your data.` })
    dialogOpen.value = false
  },
  onError: (err) => ui.pushToast({ kind: 'error', title: 'Could not create rule', message: err.message }),
})

async function submitRule() {
  if (!ruleForm.name.trim()) {
    formError.value = 'A rule name is required.'
    return
  }
  if (!ruleForm.datasetId) {
    formError.value = 'Select a dataset.'
    return
  }
  const fieldRequired = !['row_count'].includes(ruleForm.ruleType)
  if (fieldRequired && !ruleForm.fieldId) {
    formError.value = 'Select a dataset field.'
    return
  }
  const configuration: Record<string, unknown> = {}
  if (ruleForm.minimum != null) configuration.min = ruleForm.minimum
  if (ruleForm.maximum != null) configuration.max = ruleForm.maximum
  if (ruleForm.values.trim())
    configuration.values = ruleForm.values
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
  if (ruleForm.pattern.trim()) configuration.pattern = ruleForm.pattern.trim()
  if (ruleForm.ruleType === 'freshness' && ruleForm.maximum != null) {
    delete configuration.max
    configuration.max_age_hours = ruleForm.maximum
  }
  if (ruleForm.ruleType === 'range' && configuration.min == null && configuration.max == null) {
    formError.value = 'Enter a minimum or maximum value.'
    return
  }
  formError.value = ''
  await createRule.mutate({
    datasetId: ruleForm.datasetId,
    fieldId: ruleForm.fieldId || undefined,
    name: ruleForm.name.trim(),
    ruleType: ruleForm.ruleType,
    severity: ruleForm.severity,
    configuration,
  })
}

const runQuality = useMutation((datasetId: string) => datasetService.runQuality(datasetId), {
  invalidate: ['quality:rules', 'datasets:list'],
  onSuccess: (job) =>
    ui.pushToast({
      kind: 'success',
      title: 'Quality evaluation queued',
      message: `Job ${job.id.slice(0, 8)} will update the quality history.`,
    }),
  onError: (err) => ui.pushToast({ kind: 'error', title: 'Evaluation could not start', message: err.message }),
})
async function runAll(): Promise<void> {
  const selected = ruleForm.datasetId || datasetOptions.value[0]?.value
  if (!selected) {
    ui.pushToast({ kind: 'warning', title: 'No dataset', message: 'Create or discover a dataset first.' })
    return
  }
  await runQuality.mutate(selected)
}

/* ---- incidents table + drawer ---- */
const incidentColumns: Column<QualityIncident>[] = [
  { key: 'rule', label: 'Rule', width: '30%' },
  { key: 'dataset', label: 'Dataset' },
  { key: 'severity', label: 'Severity' },
  { key: 'status', label: 'Status' },
  { key: 'owner', label: 'Owner' },
  { key: 'openedAt', label: 'Opened', align: 'right' },
]

const drawerOpen = ref(false)
const activeIncident = ref<QualityIncident | undefined>(undefined)

function openIncident(row: QualityIncident) {
  activeIncident.value = row
  drawerOpen.value = true
}
async function rerunIncident() {
  if (!activeIncident.value?.datasetId) return
  await runQuality.mutate(activeIncident.value.datasetId)
  drawerOpen.value = false
}
</script>

<template>
  <div class="dq">
    <VipPageHeader
      title="Data quality"
      description="Monitor quality rules and triage open incidents across your datasets."
    >
      <template #actions>
        <VipButton variant="secondary" icon="refresh" :loading="runQuality.isPending.value" @click="runAll">
          Run evaluation
        </VipButton>
        <VipButton variant="primary" icon="plus" @click="openDialog">New rule</VipButton>
      </template>
    </VipPageHeader>

    <!-- RULES -->
    <section class="dq__section">
      <h2 class="dq__section-title">Quality rules</h2>
      <VipCard :padded="false">
        <VipTable
          :columns="ruleColumns"
          :rows="rules ?? []"
          :row-key="(r) => r.id"
          :loading="rulesLoading"
          density="compact"
          empty-title="No rules yet"
          empty-description="Create your first quality rule to start monitoring."
        >
          <template #cell-name="{ row }"
            ><span class="dq__rule-name">{{ row.name }}</span></template
          >
          <template #cell-dimension="{ row }"
            ><VipBadge tone="neutral" variant="soft" size="sm">{{ row.dimension }}</VipBadge></template
          >
          <template #cell-severity="{ row }"
            ><VipBadge :tone="severityTone(row.severity)" variant="soft" size="sm">{{
              row.severity
            }}</VipBadge></template
          >
          <template #cell-status="{ row }"
            ><VipBadge :tone="RULE_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge></template
          >
          <template #cell-passRate="{ row }"
            ><span class="dq__num">{{ row.passRate == null ? 'Not evaluated' : `${row.passRate}%` }}</span></template
          >
          <template #cell-lastRun="{ row }"
            ><span class="dq__muted">{{ relativeTime(row.lastRun) }}</span></template
          >
        </VipTable>
      </VipCard>
    </section>

    <section class="dq__section">
      <div class="dq__section-head">
        <h2 class="dq__section-title">Evaluation history</h2>
        <VipSelect v-model="ruleForm.datasetId" :options="datasetOptions" size="sm" aria-label="History dataset" />
      </div>
      <VipCard>
        <div v-if="historyLoading" class="dq__muted">Loading evaluation history…</div>
        <div v-else-if="!history?.length" class="dq__muted">This dataset has not been evaluated.</div>
        <div v-else class="dq__history">
          <div v-for="evaluation in history" :key="evaluation.id" class="dq__history-row">
            <div>
              <strong>{{ evaluation.score == null ? 'Not scored' : `${evaluation.score}%` }}</strong>
              <span>{{ relativeTime(evaluation.completedAt ?? evaluation.createdAt) }}</span>
            </div>
            <VipBadge
              :tone="
                evaluation.status === 'completed'
                  ? evaluation.failing
                    ? 'danger'
                    : evaluation.warning
                      ? 'warning'
                      : 'success'
                  : 'neutral'
              "
              size="sm"
            >
              {{ evaluation.status }}
            </VipBadge>
            <span>
              {{ evaluation.passing }} pass · {{ evaluation.warning }} warning · {{ evaluation.failing }} fail ·
              {{ evaluation.unknown }} unknown
            </span>
          </div>
        </div>
      </VipCard>
    </section>

    <!-- INCIDENTS -->
    <section class="dq__section">
      <h2 class="dq__section-title">Open incidents</h2>
      <VipCard :padded="false">
        <VipTable
          :columns="incidentColumns"
          :rows="incidents ?? []"
          :row-key="(r) => r.id"
          :loading="incidentsLoading"
          density="compact"
          clickable
          empty-title="No incidents"
          empty-description="All quality checks are currently passing."
          @row-click="openIncident"
        >
          <template #cell-rule="{ row }"
            ><span class="dq__rule-name">{{ row.rule }}</span></template
          >
          <template #cell-dataset="{ row }"
            ><span class="dq__mono">{{ row.dataset }}</span></template
          >
          <template #cell-severity="{ row }"
            ><VipBadge :tone="severityTone(row.severity)" variant="soft" size="sm">{{
              row.severity
            }}</VipBadge></template
          >
          <template #cell-status="{ row }"
            ><VipBadge :tone="INCIDENT_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge></template
          >
          <template #cell-openedAt="{ row }"
            ><span class="dq__muted">{{ relativeTime(row.openedAt) }}</span></template
          >
        </VipTable>
      </VipCard>
    </section>

    <!-- NEW RULE DIALOG -->
    <VipDialog
      :open="dialogOpen"
      title="New quality rule"
      description="Define a check to run against a dataset dimension."
      size="md"
      @close="dialogOpen = false"
    >
      <div class="dq__form">
        <VipSelect
          v-model="ruleForm.datasetId"
          :options="datasetOptions"
          label="Dataset"
          required
          @update:model-value="ruleForm.fieldId = ''"
        />
        <VipInput v-model="ruleForm.name" label="Rule name" required placeholder="e.g. orders.amount >= 0" />
        <div class="dq__form-row">
          <VipSelect v-model="ruleForm.ruleType" :options="ruleTypeOptions" label="Rule type" />
          <VipSelect v-model="ruleForm.severity" :options="severityOptions" label="Severity" />
        </div>
        <VipSelect
          v-if="ruleForm.ruleType !== 'row_count'"
          v-model="ruleForm.fieldId"
          :options="fieldOptions"
          label="Dataset field"
          required
        />
        <div v-if="ruleForm.ruleType === 'range' || ruleForm.ruleType === 'row_count'" class="dq__form-row">
          <VipInput v-model.number="ruleForm.minimum" type="number" label="Minimum" />
          <VipInput v-model.number="ruleForm.maximum" type="number" label="Maximum" />
        </div>
        <VipInput
          v-if="ruleForm.ruleType === 'accepted_values'"
          v-model="ruleForm.values"
          label="Accepted values"
          help="Comma-separated values."
        />
        <VipInput v-if="ruleForm.ruleType === 'regex'" v-model="ruleForm.pattern" label="Regular expression" />
        <VipInput
          v-if="ruleForm.ruleType === 'freshness'"
          v-model.number="ruleForm.maximum"
          type="number"
          label="Maximum age (hours)"
        />
        <p v-if="formError" class="dq__form-error">{{ formError }}</p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="dialogOpen = false">Cancel</VipButton>
        <VipButton variant="primary" icon="check" :loading="createRule.isPending.value" @click="submitRule"
          >Create rule</VipButton
        >
      </template>
    </VipDialog>

    <!-- INCIDENT DRAWER -->
    <VipDrawer :open="drawerOpen" title="Incident" :width="460" @close="drawerOpen = false">
      <div v-if="activeIncident" class="dq__incident">
        <h3 class="dq__incident-title">{{ activeIncident.rule }}</h3>
        <div class="dq__incident-badges">
          <VipBadge :tone="severityTone(activeIncident.severity)" variant="soft"
            >{{ activeIncident.severity }} severity</VipBadge
          >
          <VipBadge :tone="INCIDENT_TONE[activeIncident.status]" variant="soft">{{ activeIncident.status }}</VipBadge>
        </div>

        <dl class="dq__incident-facts">
          <div class="dq__incident-fact">
            <dt>Dataset</dt>
            <dd class="dq__mono">{{ activeIncident.dataset }}</dd>
          </div>
          <div class="dq__incident-fact">
            <dt>Owner</dt>
            <dd>{{ activeIncident.owner }}</dd>
          </div>
          <div class="dq__incident-fact">
            <dt>Opened</dt>
            <dd>{{ relativeTime(activeIncident.openedAt) }}</dd>
          </div>
          <div class="dq__incident-fact">
            <dt>Incident ID</dt>
            <dd class="dq__mono">{{ activeIncident.id }}</dd>
          </div>
          <div v-if="activeIncident.observed != null" class="dq__incident-fact">
            <dt>Observed</dt>
            <dd>{{ activeIncident.observed }}</dd>
          </div>
          <div v-if="activeIncident.expected != null" class="dq__incident-fact">
            <dt>Expected</dt>
            <dd>{{ activeIncident.expected }}</dd>
          </div>
        </dl>

        <div v-if="activeIncident.message" class="dq__issue-message">{{ activeIncident.message }}</div>
        <div v-if="activeIncident.issueDetails?.length" class="dq__issues">
          <h4>Issue samples</h4>
          <dl v-for="(issue, index) in activeIncident.issueDetails" :key="index">
            <div v-for="(value, key) in issue" :key="key">
              <dt>{{ String(key).replace(/_/g, ' ') }}</dt>
              <dd>{{ value }}</dd>
            </div>
          </dl>
        </div>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="drawerOpen = false">Close</VipButton>
        <VipButton variant="primary" icon="refresh" :loading="runQuality.isPending.value" @click="rerunIncident">
          Re-run evaluation
        </VipButton>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.dq {
  max-width: 1280px;
  margin: 0 auto;
}
.dq__section {
  margin-bottom: var(--vip-sp-8);
}
.dq__section-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-5);
}
.dq__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
}
.dq__history {
  display: flex;
  flex-direction: column;
}
.dq__history-row {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) auto minmax(260px, 2fr);
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.dq__history-row > div {
  display: flex;
  flex-direction: column;
}
.dq__rule-name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.dq__mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.dq__muted {
  color: var(--vip-text-muted);
}
.dq__num {
  font-variant-numeric: tabular-nums;
}

.dq__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.dq__form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-6);
}
.dq__form-error {
  font-size: var(--vip-fs-sm);
  color: var(--vip-danger-text);
}

.dq__incident {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.dq__incident-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.dq__incident-badges {
  display: flex;
  gap: var(--vip-sp-3);
}
.dq__incident-facts {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  overflow: hidden;
}
.dq__incident-fact {
  display: flex;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-4) var(--vip-sp-5);
}
.dq__incident-fact:not(:last-child) {
  border-bottom: 1px solid var(--vip-border-subtle);
}
.dq__incident-fact dt {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.dq__incident-fact dd {
  font-size: var(--vip-fs-md);
  color: var(--vip-text-primary);
  font-weight: var(--vip-fw-medium);
}
.dq__issue-message {
  padding: var(--vip-sp-4);
  color: var(--vip-danger-text);
  background: var(--vip-danger-soft);
  border-radius: var(--vip-radius-md);
}
.dq__issues dl {
  margin-top: var(--vip-sp-3);
  padding: var(--vip-sp-3);
  background: var(--vip-surface-2);
  border-radius: var(--vip-radius-md);
}
.dq__issues dl div {
  display: flex;
  justify-content: space-between;
  gap: var(--vip-sp-4);
}

.dq__workflow {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.dq__workflow-title {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.dq__workflow-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: var(--vip-sp-3);
}
.dq__workflow-steps li {
  flex: 1;
  text-align: center;
  padding: var(--vip-sp-3) var(--vip-sp-4);
  font-size: var(--vip-fs-xs);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
}
.dq__workflow-steps li.is-active {
  background: var(--vip-brand-soft);
  border-color: var(--vip-brand-500);
  color: var(--vip-brand-text);
  font-weight: var(--vip-fw-medium);
}

@media (max-width: 640px) {
  .dq__form-row {
    grid-template-columns: 1fr;
  }
}
</style>
