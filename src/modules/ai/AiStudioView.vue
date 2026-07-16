<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import {
  aiService,
  AI_MODELS,
  AI_TOOLS,
  type Assistant,
  type PublishStatus,
} from './ai.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipCheckbox from '@/shared/ui/VipCheckbox.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()

const tab = ref('assistants')
const tabs = [
  { value: 'assistants', label: 'Assistants' },
  { value: 'prompts', label: 'Prompts' },
  { value: 'models', label: 'Models' },
  { value: 'knowledge', label: 'Knowledge' },
  { value: 'tools', label: 'Tools' },
  { value: 'tests', label: 'Test sessions' },
]

const { data: assistants, isLoading } = useQuery('ai:assistants', () => aiService.listAssistants())
const { data: knowledge } = useQuery('ai:studio:knowledge', () => aiService.listKnowledge())

const STATUS_TONE: Record<PublishStatus, 'success' | 'neutral'> = { published: 'success', draft: 'neutral' }
const modelLabel = (v: string): string => AI_MODELS.find((m) => m.value === v)?.label ?? v

const columns: Column<Assistant>[] = [
  { key: 'name', label: 'Assistant', width: '40%' },
  { key: 'model', label: 'Model' },
  { key: 'tools', label: 'Tools', align: 'center' },
  { key: 'status', label: 'Status' },
]

/* ---- Assistant Builder ---- */
const builderOpen = ref(false)
const safety = reactive({ pii: true, restrictKnowledge: true, allowWebFetch: false })
const form = reactive({
  name: '',
  description: '',
  instructions: '',
  model: 'veltrix-reasoning',
  knowledge: [] as string[],
  tools: [] as string[],
})

function openBuilder(): void {
  form.name = ''
  form.description = ''
  form.instructions = ''
  form.model = 'veltrix-reasoning'
  form.knowledge = []
  form.tools = []
  safety.pii = true
  safety.restrictKnowledge = true
  safety.allowWebFetch = false
  builderOpen.value = true
}

function toggleIn(list: string[], value: string): void {
  const idx = list.indexOf(value)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(value)
}

function save(status: PublishStatus | 'test'): void {
  if (!form.name.trim()) {
    ui.pushToast({ kind: 'warning', title: 'Name required', message: 'Give the assistant a name before saving.' })
    return
  }
  if (status === 'test') {
    ui.pushToast({ kind: 'info', title: 'Test session started', message: `Sandbox spun up for “${form.name}”.` })
    return
  }
  ui.pushToast({
    kind: 'success',
    title: status === 'published' ? 'Assistant published' : 'Draft saved',
    message: `“${form.name}” saved as ${status}.`,
  })
  builderOpen.value = false
}

/* ---- Mock content for the other tabs ---- */
interface PromptEntry { id: string; name: string; version: string; owner: string; updatedAt: string; uses: number }
const prompts: PromptEntry[] = [
  { id: 'p1', name: 'Revenue variance explainer', version: 'v4', owner: 'RevOps', updatedAt: relativeTime(new Date(Date.now() - 36e5).toISOString()), uses: 1240 },
  { id: 'p2', name: 'Dataset summarizer', version: 'v2', owner: 'Data Platform', updatedAt: relativeTime(new Date(Date.now() - 72e5).toISOString()), uses: 860 },
  { id: 'p3', name: 'Exec narrative', version: 'v7', owner: 'Finance', updatedAt: relativeTime(new Date(Date.now() - 864e5).toISOString()), uses: 402 },
  { id: 'p4', name: 'SQL guardrail preamble', version: 'v1', owner: 'Governance', updatedAt: relativeTime(new Date(Date.now() - 6048e5).toISOString()), uses: 3110 },
]

const modelCatalog = [
  { id: 'veltrix-reasoning-pro', label: 'Veltrix Reasoning Pro', ctx: '200K context', tone: 'brand' as const, note: 'Deep multi-step analysis' },
  { id: 'veltrix-reasoning', label: 'Veltrix Reasoning', ctx: '128K context', tone: 'info' as const, note: 'Balanced default' },
  { id: 'veltrix-fast', label: 'Veltrix Fast', ctx: '32K context', tone: 'success' as const, note: 'Low-latency lookups' },
  { id: 'veltrix-analyst', label: 'Veltrix Analyst', ctx: '128K context', tone: 'warning' as const, note: 'Tuned for metrics & SQL' },
]

const testSessions = [
  { id: 't1', assistant: 'Revenue Analyst', turns: 12, verdict: 'pass', when: relativeTime(new Date(Date.now() - 18e5).toISOString()) },
  { id: 't2', assistant: 'Executive Briefer', turns: 6, verdict: 'review', when: relativeTime(new Date(Date.now() - 54e5).toISOString()) },
  { id: 't3', assistant: 'Data Catalog Guide', turns: 20, verdict: 'pass', when: relativeTime(new Date(Date.now() - 172e5).toISOString()) },
]

const knowledgeOptions = computed(() => knowledge.value ?? [])
</script>

<template>
  <div class="studio">
    <VipPageHeader title="AI Studio" description="Build, test and govern assistants, prompts and models for your workspace.">
      <template #actions>
        <VipButton v-if="tab === 'assistants'" variant="primary" icon="plus" @click="openBuilder">
          New assistant
        </VipButton>
      </template>
      <template #tabs>
        <VipTabs v-model="tab" :tabs="tabs" />
      </template>
    </VipPageHeader>

    <!-- Assistants -->
    <VipCard v-if="tab === 'assistants'" :padded="false">
      <VipTable
        :columns="columns"
        :rows="assistants ?? []"
        :row-key="(r) => r.id"
        :loading="isLoading"
        empty-title="No assistants yet"
        empty-description="Create your first assistant to expose grounded chat to your team."
      >
        <template #cell-name="{ row }">
          <div class="studio__name">
            <span class="studio__name-icon"><VipIcon name="sparkles" :size="15" /></span>
            <div class="studio__name-text">
              <span class="studio__name-title">{{ row.name }}</span>
              <span class="studio__name-desc">{{ row.description }}</span>
            </div>
          </div>
        </template>
        <template #cell-model="{ row }">
          <span class="studio__muted">{{ modelLabel(row.model) }}</span>
        </template>
        <template #cell-tools="{ row }">
          <VipBadge tone="neutral" variant="soft" size="sm">{{ row.tools.length }}</VipBadge>
        </template>
        <template #cell-status="{ row }">
          <VipBadge :tone="STATUS_TONE[row.status]" variant="soft" size="sm">{{ row.status }}</VipBadge>
        </template>
      </VipTable>
    </VipCard>

    <!-- Prompts -->
    <VipCard v-else-if="tab === 'prompts'" :padded="false">
      <div class="studio__list">
        <div v-for="p in prompts" :key="p.id" class="studio__row">
          <div class="studio__row-main">
            <span class="studio__name-icon"><VipIcon name="text" :size="15" /></span>
            <div class="studio__name-text">
              <span class="studio__name-title">{{ p.name }}</span>
              <span class="studio__name-desc">Owner: {{ p.owner }} · Updated {{ p.updatedAt }}</span>
            </div>
          </div>
          <div class="studio__row-meta">
            <VipBadge tone="brand" variant="soft" size="sm">{{ p.version }}</VipBadge>
            <span class="studio__muted">{{ p.uses.toLocaleString() }} uses</span>
            <VipButton variant="ghost" size="xs" icon="dots" title="Prompt actions" @click="() => {}" />
          </div>
        </div>
      </div>
    </VipCard>

    <!-- Models -->
    <div v-else-if="tab === 'models'" class="studio__grid">
      <VipCard v-for="m in modelCatalog" :key="m.id">
        <div class="studio__model-head">
          <VipBadge :tone="m.tone" variant="soft" size="sm">{{ m.ctx }}</VipBadge>
          <VipIcon name="brain" :size="16" />
        </div>
        <h3 class="studio__model-name">{{ m.label }}</h3>
        <p class="studio__model-note">{{ m.note }}</p>
      </VipCard>
    </div>

    <!-- Knowledge -->
    <div v-else-if="tab === 'knowledge'" class="studio__grid">
      <VipCard v-for="k in knowledgeOptions" :key="k.id">
        <div class="studio__model-head">
          <VipBadge :tone="k.status === 'ready' ? 'success' : k.status === 'indexing' ? 'info' : 'danger'" variant="soft" size="sm">
            {{ k.status }}
          </VipBadge>
          <VipIcon name="book" :size="16" />
        </div>
        <h3 class="studio__model-name">{{ k.name }}</h3>
        <p class="studio__model-note">{{ k.documents.toLocaleString() }} documents · indexed {{ relativeTime(k.lastIndexed) }}</p>
      </VipCard>
    </div>

    <!-- Tools -->
    <div v-else-if="tab === 'tools'" class="studio__grid">
      <VipCard v-for="t in AI_TOOLS" :key="t.value">
        <div class="studio__model-head">
          <span class="studio__name-icon"><VipIcon :name="t.icon" :size="15" /></span>
          <VipBadge tone="neutral" variant="outline" size="sm">tool</VipBadge>
        </div>
        <h3 class="studio__model-name">{{ t.label }}</h3>
        <p class="studio__model-note">Grantable capability for assistants and agents.</p>
      </VipCard>
    </div>

    <!-- Test sessions -->
    <VipCard v-else :padded="false">
      <div class="studio__list">
        <div v-for="s in testSessions" :key="s.id" class="studio__row">
          <div class="studio__row-main">
            <span class="studio__name-icon"><VipIcon name="play" :size="15" /></span>
            <div class="studio__name-text">
              <span class="studio__name-title">{{ s.assistant }}</span>
              <span class="studio__name-desc">{{ s.turns }} turns · {{ s.when }}</span>
            </div>
          </div>
          <VipBadge :tone="s.verdict === 'pass' ? 'success' : 'warning'" variant="soft" size="sm">{{ s.verdict }}</VipBadge>
        </div>
      </div>
    </VipCard>

    <!-- Assistant Builder -->
    <VipDrawer :open="builderOpen" title="New assistant" :width="520" @close="builderOpen = false">
      <div class="studio__form">
        <VipInput v-model="form.name" label="Name" placeholder="e.g. Revenue Analyst" required />
        <VipInput v-model="form.description" label="Description" placeholder="What this assistant helps with" />
        <VipTextarea
          v-model="form.instructions"
          label="Instructions"
          :rows="6"
          placeholder="Describe the assistant's role, tone and guardrails…"
          help="These system instructions steer every response. Do not put secrets here."
        />
        <VipSelect v-model="form.model" label="Model" :options="AI_MODELS" />

        <div class="studio__group">
          <span class="studio__group-label">Knowledge bases</span>
          <div class="studio__checks">
            <VipCheckbox
              v-for="k in knowledgeOptions"
              :key="k.id"
              :model-value="form.knowledge.includes(k.id)"
              :label="k.name"
              @update:model-value="toggleIn(form.knowledge, k.id)"
            />
          </div>
        </div>

        <div class="studio__group">
          <span class="studio__group-label">Tools</span>
          <div class="studio__checks">
            <VipCheckbox
              v-for="t in AI_TOOLS"
              :key="t.value"
              :model-value="form.tools.includes(t.value)"
              :label="t.label"
              @update:model-value="toggleIn(form.tools, t.value)"
            />
          </div>
        </div>

        <div class="studio__group">
          <span class="studio__group-label">Safety</span>
          <div class="studio__switches">
            <VipSwitch v-model="safety.pii" label="Redact PII in responses" />
            <VipSwitch v-model="safety.restrictKnowledge" label="Restrict answers to attached knowledge" />
            <VipSwitch v-model="safety.allowWebFetch" label="Allow external web fetch" />
          </div>
        </div>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="save('test')">Test</VipButton>
        <VipButton variant="secondary" @click="save('draft')">Save draft</VipButton>
        <VipButton variant="primary" icon="check" @click="save('published')">Publish</VipButton>
      </template>
    </VipDrawer>
  </div>
</template>

<style scoped>
.studio { max-width: 1280px; margin: 0 auto; }
.studio__name { display: flex; align-items: center; gap: var(--vip-sp-5); }
.studio__name-icon {
  width: 32px; height: 32px; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--vip-radius-md); background: var(--vip-brand-soft); color: var(--vip-brand-text);
}
.studio__name-text { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.studio__name-title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.studio__name-desc { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.studio__muted { color: var(--vip-text-muted); font-size: var(--vip-fs-sm); }

.studio__list { display: flex; flex-direction: column; }
.studio__row { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-5); padding: var(--vip-sp-5) var(--vip-sp-6); border-bottom: 1px solid var(--vip-border-subtle); }
.studio__row:last-child { border-bottom: none; }
.studio__row-main { display: flex; align-items: center; gap: var(--vip-sp-5); min-width: 0; }
.studio__row-meta { display: flex; align-items: center; gap: var(--vip-sp-5); }

.studio__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--vip-sp-6); }
.studio__model-head { display: flex; align-items: center; justify-content: space-between; color: var(--vip-text-muted); margin-bottom: var(--vip-sp-5); }
.studio__model-name { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-2); }
.studio__model-note { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }

.studio__form { display: flex; flex-direction: column; gap: var(--vip-sp-6); }
.studio__group { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.studio__group-label { font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-medium); color: var(--vip-text-secondary); }
.studio__checks { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-4); }
.studio__switches { display: flex; flex-direction: column; gap: var(--vip-sp-5); }
</style>
