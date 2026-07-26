<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { insightsService, SUGGESTED_QUESTIONS } from './insights.service'
import { semanticStudioService } from '@/modules/semantic/semantic.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import type { Insight } from '@/shared/types/insight'
import type { SemanticModel } from '@/shared/types/semantic'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import InsightCard from './InsightCard.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const modelId = ref('')
const models = ref<SemanticModel[]>([])
const hasModel = computed(() => Boolean(modelId.value))
const filter = ref<'all' | 'positive' | 'negative'>('all')
const { data, isLoading, refetch } = useQuery(
  () => `insights:${modelId.value}`,
  () => insightsService.list(modelId.value),
  { enabled: hasModel },
)

const generated = ref<Insight[]>([])
const nlq = ref('')
const asking = ref(false)
const nlqEnabled = computed(() => platform.flagEnabled('insights-nlq'))

onMounted(async () => {
  models.value = (await semanticStudioService.listModels()).filter((model) => model.certified)
  modelId.value = models.value[0]?.id ?? ''
})

const cards = computed(() => {
  const list = [...generated.value, ...(data.value ?? [])]
  if (filter.value === 'positive') return list.filter((i) => i.sentiment === 'positive')
  if (filter.value === 'negative') return list.filter((i) => i.sentiment === 'negative')
  return list
})

async function ask(q?: string) {
  const question = q ?? nlq.value
  if (!question.trim()) return
  asking.value = true
  const insight = await insightsService.explain(question)
  generated.value.unshift(insight)
  nlq.value = ''
  asking.value = false
}

function onPin(i: Insight) {
  i.pinned = !i.pinned
  ui.pushToast({
    kind: 'success',
    title: i.pinned ? 'Pinned to dashboard' : 'Unpinned',
    message: i.pinned ? 'Added to "Executive Overview".' : undefined,
  })
}
function onSave(i: Insight) {
  i.saved = !i.saved
  ui.pushToast({ kind: 'success', title: i.saved ? 'Insight saved' : 'Removed from saved' })
}
function onShare() {
  ui.pushToast({ kind: 'info', title: 'Share insight', message: 'Sharing connects to backend delivery services.' })
}
function onExplain(i: Insight) {
  ask(`Explain the driver behind "${i.title}"`)
}
</script>

<template>
  <div class="insights">
    <VipPageHeader
      title="Insights"
      description="Automatically surfaced findings, trends and anomalies across your data."
    >
      <template #actions>
        <VipSelect
          v-model="modelId"
          :options="models.map((m) => ({ value: m.id, label: m.label }))"
          size="sm"
          @update:model-value="refetch()"
        />
        <VipSegmented
          v-model="filter"
          :options="[
            { value: 'all', label: 'All' },
            { value: 'positive', label: 'Positive' },
            { value: 'negative', label: 'Attention' },
          ]"
          size="sm"
        />
      </template>
    </VipPageHeader>

    <!-- NL query -->
    <div v-if="nlqEnabled" class="insights__nlq">
      <div class="insights__nlq-input">
        <VipIcon name="sparkles" :size="17" />
        <input v-model="nlq" placeholder="Ask a question about your data…" @keyup.enter="ask()" />
        <VipButton variant="primary" size="sm" :loading="asking" icon="chevronRight" @click="ask()">Ask</VipButton>
      </div>
      <div class="insights__suggestions">
        <button v-for="q in SUGGESTED_QUESTIONS" :key="q.id" class="insights__chip" @click="ask(q.text)">
          {{ q.text }}
        </button>
      </div>
    </div>

    <VipAlert v-if="!models.length && !isLoading" tone="info" title="No published semantic model">
      Publish a semantic model before evaluating governed insights.
    </VipAlert>

    <div v-if="isLoading" class="insights__grid">
      <VipSkeleton v-for="n in 4" :key="n" height="280px" block />
    </div>
    <div v-else class="insights__grid">
      <InsightCard
        v-for="i in cards"
        :key="i.id"
        :insight="i"
        @explain="onExplain"
        @pin="onPin"
        @save="onSave"
        @share="onShare"
      />
    </div>

    <div v-if="!isLoading && !cards.length" class="insights__empty">
      <VipBadge tone="neutral">No insights match this filter.</VipBadge>
    </div>
  </div>
</template>

<style scoped>
.insights {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.insights__nlq {
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-lg);
  padding: var(--vip-sp-5);
}
.insights__nlq-input {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  color: var(--vip-brand-text);
}
.insights__nlq-input input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-lg);
}
.insights__suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3);
  margin-top: var(--vip-sp-5);
}
.insights__chip {
  padding: var(--vip-sp-2) var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-full);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-xs);
}
.insights__chip:hover {
  border-color: var(--vip-brand-500);
  color: var(--vip-brand-text);
}
.insights__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: var(--vip-sp-6);
  align-items: stretch;
}
.insights__empty {
  text-align: center;
  padding: var(--vip-sp-10);
}
</style>
