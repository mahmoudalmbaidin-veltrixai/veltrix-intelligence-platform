<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/shared/types/api'
import { useUiStore } from '@/shared/stores/ui'
import { pipelineService, type PipelineSchedule, type PipelineScheduleInput } from './pipelines.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const pipelineId = computed(() => String(route.params.id))

const schedules = ref<PipelineSchedule[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const creating = ref(false)
const busyId = ref<string | null>(null)
const pipelineName = ref('')

const CADENCES = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'cron', label: 'Cron expression' },
  { value: 'one_time', label: 'One time' },
]

const form = reactive<{
  name: string
  scheduleType: PipelineScheduleInput['scheduleType']
  scheduleExpression: string
  runAt: string
  timezone: string
}>({
  name: '',
  scheduleType: 'daily',
  scheduleExpression: '0 6 * * *',
  runAt: '',
  timezone: 'UTC',
})

const confirmDelete = ref<PipelineSchedule | null>(null)

function cadenceLabel(schedule: PipelineSchedule): string {
  if (schedule.scheduleType === 'cron') return `cron: ${schedule.scheduleExpression ?? ''}`
  return schedule.scheduleType
}

async function load() {
  loading.value = true
  error.value = null
  try {
    schedules.value = await pipelineService.listSchedules(pipelineId.value)
    try {
      pipelineName.value = (await pipelineService.get(pipelineId.value)).name
    } catch {
      pipelineName.value = ''
    }
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Unable to load schedules.'
    schedules.value = []
  } finally {
    loading.value = false
  }
}

const canSubmit = computed(() => {
  if (!form.name.trim()) return false
  if (form.scheduleType === 'cron') return form.scheduleExpression.trim().length > 0
  if (form.scheduleType === 'one_time') return form.runAt.trim().length > 0
  return true
})

async function create() {
  if (!canSubmit.value) return
  creating.value = true
  try {
    const input: PipelineScheduleInput = {
      name: form.name.trim(),
      scheduleType: form.scheduleType,
      timezone: form.timezone.trim() || 'UTC',
      enabled: true,
    }
    if (form.scheduleType === 'cron') input.scheduleExpression = form.scheduleExpression.trim()
    if (form.scheduleType === 'one_time') input.runAt = new Date(form.runAt).toISOString()
    await pipelineService.createSchedule(pipelineId.value, input)
    form.name = ''
    await load()
    ui.pushToast({ kind: 'success', title: 'Schedule created' })
  } catch (e) {
    ui.pushToast({
      kind: 'error',
      title: 'Could not create schedule',
      message: e instanceof ApiError ? e.message : 'Unexpected error.',
    })
  } finally {
    creating.value = false
  }
}

async function toggle(schedule: PipelineSchedule, enabled: boolean) {
  busyId.value = schedule.id
  try {
    await pipelineService.toggleSchedule(pipelineId.value, schedule, enabled)
    await load()
  } catch (e) {
    ui.pushToast({
      kind: 'error',
      title: enabled ? 'Could not resume' : 'Could not pause',
      message: e instanceof ApiError ? e.message : 'Unexpected error.',
    })
  } finally {
    busyId.value = null
  }
}

async function remove() {
  const schedule = confirmDelete.value
  if (!schedule) return
  busyId.value = schedule.id
  try {
    await pipelineService.deleteSchedule(pipelineId.value, schedule.id, schedule.rowVersion)
    confirmDelete.value = null
    await load()
    ui.pushToast({ kind: 'success', title: 'Schedule cancelled' })
  } catch (e) {
    ui.pushToast({
      kind: 'error',
      title: 'Could not cancel schedule',
      message: e instanceof ApiError ? e.message : 'Unexpected error.',
    })
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="ps">
    <VipPageHeader
      :title="pipelineName ? `Schedules — ${pipelineName}` : 'Pipeline schedules'"
      description="Run this pipeline automatically on a recurring or one-time schedule."
    >
      <VipButton variant="secondary" icon="workflow" @click="router.push(`/pipelines/${pipelineId}/runs`)">
        View runs
      </VipButton>
    </VipPageHeader>

    <VipCard>
      <h3 class="ps__title">New schedule</h3>
      <div class="ps__form">
        <VipInput v-model="form.name" label="Name" placeholder="Nightly refresh" />
        <VipSelect v-model="form.scheduleType" label="Cadence" :options="CADENCES" />
        <VipInput
          v-if="form.scheduleType === 'cron'"
          v-model="form.scheduleExpression"
          label="Cron (min hour dom mon dow)"
          placeholder="0 6 * * *"
        />
        <VipInput
          v-else-if="form.scheduleType === 'one_time'"
          v-model="form.runAt"
          type="datetime-local"
          label="Run at"
        />
        <VipInput v-model="form.timezone" label="Timezone" placeholder="UTC" />
      </div>
      <div class="ps__actions">
        <VipButton variant="primary" icon="plus" :loading="creating" :disabled="!canSubmit" @click="create">
          Create schedule
        </VipButton>
      </div>
    </VipCard>

    <VipCard>
      <h3 class="ps__title">Schedules</h3>
      <div v-if="loading" class="ps__loading"><VipSpinner label="Loading schedules…" /></div>
      <VipAlert v-else-if="error" tone="danger" title="Schedules unavailable">
        {{ error }}
        <template #actions>
          <VipButton variant="secondary" size="sm" icon="refresh" @click="load">Retry</VipButton>
        </template>
      </VipAlert>
      <VipEmptyState
        v-else-if="schedules.length === 0"
        icon="calendar"
        title="No schedules yet"
        description="Create a schedule above to run this pipeline automatically."
      />
      <ul v-else class="ps__list">
        <li v-for="s in schedules" :key="s.id" class="ps__row">
          <div class="ps__row-main">
            <span class="ps__row-name">{{ s.name }}</span>
            <div class="ps__row-meta">
              <VipBadge tone="info" variant="soft" size="sm">{{ cadenceLabel(s) }}</VipBadge>
              <VipBadge :tone="s.enabled ? 'success' : 'neutral'" variant="soft" size="sm">
                {{ s.status }}
              </VipBadge>
              <span class="ps__muted"> Next: {{ s.nextRunAt ? new Date(s.nextRunAt).toLocaleString() : '—' }} </span>
            </div>
          </div>
          <div class="ps__row-actions">
            <VipSwitch
              :model-value="s.enabled"
              :disabled="busyId === s.id"
              :aria-label="s.enabled ? 'Pause schedule' : 'Resume schedule'"
              @update:model-value="(v: boolean) => toggle(s, v)"
            />
            <VipButton
              variant="ghost"
              size="sm"
              icon="trash"
              :disabled="busyId === s.id"
              aria-label="Cancel schedule"
              @click="confirmDelete = s"
            />
          </div>
        </li>
      </ul>
    </VipCard>

    <VipConfirmDialog
      :open="confirmDelete !== null"
      title="Cancel schedule?"
      :message="`This stops future runs of “${confirmDelete?.name ?? ''}”. Run history is retained.`"
      confirm-label="Cancel schedule"
      tone="danger"
      @confirm="remove"
      @cancel="confirmDelete = null"
    />
  </div>
</template>

<style scoped>
.ps {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.ps__title {
  font-size: var(--vip-fs-md);
  margin-bottom: var(--vip-sp-4);
}
.ps__form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--vip-sp-4);
}
.ps__actions {
  margin-top: var(--vip-sp-4);
}
.ps__loading {
  padding: var(--vip-sp-6);
}
.ps__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.ps__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.ps__row-name {
  font-weight: 600;
}
.ps__row-meta {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  margin-top: var(--vip-sp-2);
  flex-wrap: wrap;
}
.ps__row-actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.ps__muted {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
}
</style>
