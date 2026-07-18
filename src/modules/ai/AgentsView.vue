<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { aiService, AI_MODELS, AI_TOOLS, type Agent, type PublishStatus } from './ai.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipCheckbox from '@/shared/ui/VipCheckbox.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const router = useRouter()
const ui = useUiStore()

const { data: agents, isLoading } = useQuery('ai:agents', () => aiService.listAgents())
const { data: knowledge } = useQuery('ai:agents:knowledge', () => aiService.listKnowledge())

const STATUS_TONE: Record<PublishStatus, 'success' | 'neutral'> = { published: 'success', draft: 'neutral' }
const modelLabel = (v: string): string => AI_MODELS.find((m) => m.value === v)?.label ?? v

const columns: Column<Agent>[] = [
  { key: 'name', label: 'Agent', width: '42%' },
  { key: 'model', label: 'Model' },
  { key: 'tools', label: 'Tools', align: 'center' },
  { key: 'status', label: 'Status' },
]

function openRuns(agent: Agent): void {
  void agent
  router.push('/ai/agent-runs')
}

/* ---- Agent Builder ---- */
const builderOpen = ref(false)
const MEMORY_OPTIONS = [
  { value: 'none', label: 'Stateless (no memory)' },
  { value: 'session', label: 'Session memory' },
  { value: 'persistent', label: 'Persistent workspace memory' },
]
const form = reactive({
  name: '',
  goal: '',
  instructions: '',
  model: 'veltrix-reasoning',
  knowledge: [] as string[],
  tools: [] as string[],
  memory: 'session',
  approvalRequired: true,
  maxSteps: 12,
  maxCostUsd: 5,
})

function openBuilder(): void {
  form.name = ''
  form.goal = ''
  form.instructions = ''
  form.model = 'veltrix-reasoning'
  form.knowledge = []
  form.tools = []
  form.memory = 'session'
  form.approvalRequired = true
  form.maxSteps = 12
  form.maxCostUsd = 5
  builderOpen.value = true
}

function toggleIn(list: string[], value: string): void {
  const idx = list.indexOf(value)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(value)
}

function save(status: PublishStatus): void {
  if (!form.name.trim() || !form.goal.trim()) {
    ui.pushToast({ kind: 'warning', title: 'Name and goal required' })
    return
  }
  ui.pushToast({
    kind: 'success',
    title: status === 'published' ? 'Agent published' : 'Draft saved',
    message: `“${form.name}” saved as ${status}.`,
  })
  builderOpen.value = false
}
</script>

<template>
  <div class="agents">
    <VipPageHeader
      title="Agents"
      description="Autonomous, tool-using agents that pursue a goal across your data platform."
    >
      <template #actions>
        <VipButton variant="tertiary" icon="run" @click="router.push('/ai/agent-runs')">View runs</VipButton>
        <VipButton variant="primary" icon="plus" @click="openBuilder">New agent</VipButton>
      </template>
    </VipPageHeader>

    <VipCard :padded="false">
      <VipTable
        :columns="columns"
        :rows="agents ?? []"
        :row-key="(r) => r.id"
        :loading="isLoading"
        clickable
        empty-title="No agents yet"
        empty-description="Create an agent to automate multi-step investigations and briefings."
        @row-click="openRuns"
      >
        <template #cell-name="{ row }">
          <div class="agents__name">
            <span class="agents__name-icon"><VipIcon name="bot" :size="15" /></span>
            <div class="agents__name-text">
              <span class="agents__name-title">{{ row.name }}</span>
              <span class="agents__name-desc">{{ row.goal }}</span>
            </div>
          </div>
        </template>
        <template #cell-model="{ row }">
          <span class="agents__muted">{{ modelLabel(row.model) }}</span>
        </template>
        <template #cell-tools="{ row }">
          <VipBadge tone="neutral" variant="soft" size="sm">{{ row.tools.length }}</VipBadge>
        </template>
        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge>
        </template>
      </VipTable>
    </VipCard>

    <!-- Agent Builder -->
    <VipDrawer :open="builderOpen" title="New agent" :width="540" @close="builderOpen = false">
      <div class="agents__form">
        <VipInput v-model="form.name" label="Name" placeholder="e.g. Incident Triage" required />
        <VipTextarea
          v-model="form.goal"
          label="Goal"
          :rows="2"
          placeholder="What outcome should this agent achieve?"
          required
        />
        <VipTextarea
          v-model="form.instructions"
          label="Instructions"
          :rows="5"
          placeholder="Operating guidance, constraints and escalation policy…"
        />
        <VipSelect v-model="form.model" label="Model" :options="AI_MODELS" />

        <div class="agents__group">
          <span class="agents__group-label">Knowledge bases</span>
          <div class="agents__checks">
            <VipCheckbox
              v-for="k in knowledge ?? []"
              :key="k.id"
              :model-value="form.knowledge.includes(k.id)"
              :label="k.name"
              @update:model-value="toggleIn(form.knowledge, k.id)"
            />
          </div>
        </div>

        <div class="agents__group">
          <span class="agents__group-label">Tools</span>
          <div class="agents__checks">
            <VipCheckbox
              v-for="t in AI_TOOLS"
              :key="t.value"
              :model-value="form.tools.includes(t.value)"
              :label="t.label"
              @update:model-value="toggleIn(form.tools, t.value)"
            />
          </div>
        </div>

        <VipSelect v-model="form.memory" label="Memory policy" :options="MEMORY_OPTIONS" />

        <div class="agents__group">
          <span class="agents__group-label">Governance</span>
          <VipSwitch v-model="form.approvalRequired" label="Require human approval for side-effecting actions" />
        </div>

        <div class="agents__group">
          <span class="agents__group-label">Limits</span>
          <div class="agents__limits">
            <VipInput v-model.number="form.maxSteps" type="number" label="Max steps" />
            <VipInput v-model.number="form.maxCostUsd" type="number" label="Max cost (USD)" prefix="$" />
          </div>
        </div>
      </div>
      <template #footer>
        <VipButton variant="secondary" @click="save('draft')">Save draft</VipButton>
        <VipButton variant="primary" icon="check" @click="save('published')">Publish</VipButton>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.agents {
  max-width: 1280px;
  margin: 0 auto;
}
.agents__name {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
}
.agents__name-icon {
  width: 32px;
  height: 32px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.agents__name-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.agents__name-title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.agents__name-desc {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.agents__muted {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}

.agents__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.agents__group {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.agents__group-label {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
}
.agents__checks {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-4);
}
.agents__limits {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-5);
}
</style>
