<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useQuery, useMutation } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import {
  datasetService,
  type QualityRule,
  type QualityRuleStatus,
  type QualityDimension,
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
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()

const { data: rules, isLoading: rulesLoading } = useQuery('quality:rules', () => datasetService.listQualityRules())
const { data: incidents, isLoading: incidentsLoading } = useQuery('quality:incidents', () => datasetService.listIncidents())

/* ---- severity / status tone maps ---- */
const RULE_TONE: Record<QualityRuleStatus, 'success' | 'warning' | 'danger'> = {
  passing: 'success',
  warning: 'warning',
  failing: 'danger',
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
interface RuleForm { name: string; dimension: QualityDimension; severity: QualitySeverity; threshold: number }
const ruleForm = reactive<RuleForm>({ name: '', dimension: 'completeness', severity: 'medium', threshold: 95 })
const formError = ref('')

const dimensionOptions: { value: string; label: string }[] = [
  { value: 'completeness', label: 'Completeness' },
  { value: 'validity', label: 'Validity' },
  { value: 'uniqueness', label: 'Uniqueness' },
  { value: 'freshness', label: 'Freshness' },
  { value: 'consistency', label: 'Consistency' },
]
const severityOptions: { value: string; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

function openDialog() {
  ruleForm.name = ''
  ruleForm.dimension = 'completeness'
  ruleForm.severity = 'medium'
  ruleForm.threshold = 95
  formError.value = ''
  dialogOpen.value = true
}

const createRule = useMutation<CreateRulePayload, QualityRule>(
  (payload) => datasetService.createRule(payload),
  {
    invalidate: ['quality:rules'],
    onSuccess: (rule) => {
      ui.pushToast({ kind: 'success', title: 'Rule created', message: `“${rule.name}” is now monitoring your data.` })
      dialogOpen.value = false
    },
    onError: (err) => ui.pushToast({ kind: 'error', title: 'Could not create rule', message: err.message }),
  },
)

async function submitRule() {
  if (!ruleForm.name.trim()) {
    formError.value = 'A rule name is required.'
    return
  }
  if (ruleForm.threshold < 0 || ruleForm.threshold > 100) {
    formError.value = 'Threshold must be between 0 and 100.'
    return
  }
  formError.value = ''
  await createRule.mutate({
    name: ruleForm.name.trim(),
    dimension: ruleForm.dimension,
    severity: ruleForm.severity,
    threshold: ruleForm.threshold,
  })
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
const resolutionNotes = ref('')

function openIncident(row: QualityIncident) {
  activeIncident.value = row
  resolutionNotes.value = ''
  drawerOpen.value = true
}
function resolveIncident() {
  if (!activeIncident.value) return
  activeIncident.value.status = 'resolved'
  ui.pushToast({ kind: 'success', title: 'Incident resolved', message: `${activeIncident.value.rule} marked as resolved.` })
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
          <template #cell-name="{ row }"><span class="dq__rule-name">{{ row.name }}</span></template>
          <template #cell-dimension="{ row }"><VipBadge tone="neutral" variant="soft" size="sm">{{ row.dimension }}</VipBadge></template>
          <template #cell-severity="{ row }"><VipBadge :tone="severityTone(row.severity)" variant="soft" size="sm">{{ row.severity }}</VipBadge></template>
          <template #cell-status="{ row }"><VipBadge :tone="RULE_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge></template>
          <template #cell-passRate="{ row }"><span class="dq__num">{{ row.passRate }}%</span></template>
          <template #cell-lastRun="{ row }"><span class="dq__muted">{{ relativeTime(row.lastRun) }}</span></template>
        </VipTable>
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
          <template #cell-rule="{ row }"><span class="dq__rule-name">{{ row.rule }}</span></template>
          <template #cell-dataset="{ row }"><span class="dq__mono">{{ row.dataset }}</span></template>
          <template #cell-severity="{ row }"><VipBadge :tone="severityTone(row.severity)" variant="soft" size="sm">{{ row.severity }}</VipBadge></template>
          <template #cell-status="{ row }"><VipBadge :tone="INCIDENT_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge></template>
          <template #cell-openedAt="{ row }"><span class="dq__muted">{{ relativeTime(row.openedAt) }}</span></template>
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
        <VipInput v-model="ruleForm.name" label="Rule name" required placeholder="e.g. orders.amount >= 0" />
        <div class="dq__form-row">
          <VipSelect v-model="ruleForm.dimension" :options="dimensionOptions" label="Dimension" />
          <VipSelect v-model="ruleForm.severity" :options="severityOptions" label="Severity" />
        </div>
        <VipInput
          v-model.number="ruleForm.threshold"
          type="number"
          label="Pass threshold (%)"
          suffix="%"
          help="Minimum pass rate before the rule is considered failing."
        />
        <p v-if="formError" class="dq__form-error">{{ formError }}</p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="dialogOpen = false">Cancel</VipButton>
        <VipButton variant="primary" icon="check" :loading="createRule.isPending.value" @click="submitRule">Create rule</VipButton>
      </template>
    </VipDialog>

    <!-- INCIDENT DRAWER -->
    <VipDrawer :open="drawerOpen" title="Incident" :width="460" @close="drawerOpen = false">
      <div v-if="activeIncident" class="dq__incident">
        <h3 class="dq__incident-title">{{ activeIncident.rule }}</h3>
        <div class="dq__incident-badges">
          <VipBadge :tone="severityTone(activeIncident.severity)" variant="soft">{{ activeIncident.severity }} severity</VipBadge>
          <VipBadge :tone="INCIDENT_TONE[activeIncident.status]" variant="soft">{{ activeIncident.status }}</VipBadge>
        </div>

        <dl class="dq__incident-facts">
          <div class="dq__incident-fact"><dt>Dataset</dt><dd class="dq__mono">{{ activeIncident.dataset }}</dd></div>
          <div class="dq__incident-fact"><dt>Owner</dt><dd>{{ activeIncident.owner }}</dd></div>
          <div class="dq__incident-fact"><dt>Opened</dt><dd>{{ relativeTime(activeIncident.openedAt) }}</dd></div>
          <div class="dq__incident-fact"><dt>Incident ID</dt><dd class="dq__mono">{{ activeIncident.id }}</dd></div>
        </dl>

        <div class="dq__workflow">
          <span class="dq__workflow-title">Workflow</span>
          <ol class="dq__workflow-steps">
            <li :class="{ 'is-active': activeIncident.status !== 'resolved' }">Detected</li>
            <li :class="{ 'is-active': activeIncident.status === 'investigating' }">Investigating</li>
            <li :class="{ 'is-active': activeIncident.status === 'resolved' }">Resolved</li>
          </ol>
        </div>

        <VipTextarea
          v-model="resolutionNotes"
          label="Resolution notes"
          :rows="4"
          placeholder="Describe the root cause and remediation…"
        />
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="drawerOpen = false">Close</VipButton>
        <VipButton
          variant="primary"
          icon="check"
          :disabled="activeIncident?.status === 'resolved'"
          @click="resolveIncident"
        >
          {{ activeIncident?.status === 'resolved' ? 'Resolved' : 'Mark resolved' }}
        </VipButton>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.dq { max-width: 1280px; margin: 0 auto; }
.dq__section { margin-bottom: var(--vip-sp-8); }
.dq__section-title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-5); }
.dq__rule-name { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.dq__mono { font-family: var(--vip-font-mono); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
.dq__muted { color: var(--vip-text-muted); }
.dq__num { font-variant-numeric: tabular-nums; }

.dq__form { display: flex; flex-direction: column; gap: var(--vip-sp-6); }
.dq__form-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-6); }
.dq__form-error { font-size: var(--vip-fs-sm); color: var(--vip-danger-text); }

.dq__incident { display: flex; flex-direction: column; gap: var(--vip-sp-6); }
.dq__incident-title { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); }
.dq__incident-badges { display: flex; gap: var(--vip-sp-3); }
.dq__incident-facts { display: flex; flex-direction: column; gap: 0; border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); overflow: hidden; }
.dq__incident-fact { display: flex; justify-content: space-between; gap: var(--vip-sp-5); padding: var(--vip-sp-4) var(--vip-sp-5); }
.dq__incident-fact:not(:last-child) { border-bottom: 1px solid var(--vip-border-subtle); }
.dq__incident-fact dt { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.dq__incident-fact dd { font-size: var(--vip-fs-md); color: var(--vip-text-primary); font-weight: var(--vip-fw-medium); }

.dq__workflow { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.dq__workflow-title { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.dq__workflow-steps { list-style: none; margin: 0; padding: 0; display: flex; gap: var(--vip-sp-3); }
.dq__workflow-steps li {
  flex: 1; text-align: center;
  padding: var(--vip-sp-3) var(--vip-sp-4);
  font-size: var(--vip-fs-xs);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
}
.dq__workflow-steps li.is-active { background: var(--vip-brand-soft); border-color: var(--vip-brand-500); color: var(--vip-brand-text); font-weight: var(--vip-fw-medium); }

@media (max-width: 640px) { .dq__form-row { grid-template-columns: 1fr; } }
</style>
