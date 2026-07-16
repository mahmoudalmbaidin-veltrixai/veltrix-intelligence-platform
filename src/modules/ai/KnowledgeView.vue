<script setup lang="ts">
import { ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import { aiService, type KnowledgeBase, type KnowledgeStatus } from './ai.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const ui = useUiStore()
const { data, isLoading } = useQuery('ai:knowledge:list', () => aiService.listKnowledge())

const STATUS_TONE: Record<KnowledgeStatus, 'success' | 'info' | 'danger'> = {
  ready: 'success',
  indexing: 'info',
  error: 'danger',
}

/* ---- Detail drawer ---- */
const selected = ref<KnowledgeBase | null>(null)
const searchTest = ref('')
interface Chunk { id: string; doc: string; score: number; text: string }
const chunks = ref<Chunk[]>([])
const searching = ref(false)

const MOCK_DOCS = [
  { id: 'd1', name: 'Q3 Financial Plan.pdf', pages: 42, status: 'ready' as const },
  { id: 'd2', name: 'Revenue Recognition Policy.docx', pages: 18, status: 'ready' as const },
  { id: 'd3', name: 'FY26 Budget Model.xlsx', pages: 6, status: 'ready' as const },
  { id: 'd4', name: 'Board Deck — Q2.pptx', pages: 31, status: 'indexing' as const },
]

function openDetail(kb: KnowledgeBase): void {
  selected.value = kb
  searchTest.value = ''
  chunks.value = []
}

function reindex(): void {
  if (!selected.value) return
  ui.pushToast({ kind: 'info', title: 'Reindex queued', message: `“${selected.value.name}” will be re-embedded shortly.` })
}

function runSearchTest(): void {
  const q = searchTest.value.trim()
  if (!q) return
  searching.value = true
  chunks.value = []
  setTimeout(() => {
    chunks.value = [
      { id: 'c1', doc: 'Q3 Financial Plan.pdf', score: 0.92, text: `…the Q3 revenue target of $49.7M assumes enterprise renewal timing holds within the quarter, matching “${q}”…` },
      { id: 'c2', doc: 'Revenue Recognition Policy.docx', score: 0.81, text: '…recognized ratably over the contract term; multi-year deals are amortized per ASC 606…' },
      { id: 'c3', doc: 'FY26 Budget Model.xlsx', score: 0.74, text: '…APAC new-logo expansion contributes an incremental 0.6M against plan in the base case…' },
    ]
    searching.value = false
  }, 600)
}

/* ---- New KB dialog ---- */
const createOpen = ref(false)
const newName = ref('')
const dragOver = ref(false)

function createKb(): void {
  if (!newName.value.trim()) {
    ui.pushToast({ kind: 'warning', title: 'Name required' })
    return
  }
  ui.pushToast({ kind: 'success', title: 'Knowledge base created', message: `“${newName.value}” is ready for documents.` })
  createOpen.value = false
  newName.value = ''
}
</script>

<template>
  <div class="kb">
    <VipPageHeader title="Knowledge" description="Curated document collections that ground assistant and agent answers.">
      <template #actions>
        <VipButton variant="primary" icon="plus" @click="createOpen = true">New knowledge base</VipButton>
      </template>
    </VipPageHeader>

    <div v-if="isLoading" class="kb__loading"><VipSpinner label="Loading knowledge bases" /></div>

    <VipEmptyState
      v-else-if="!data?.length"
      icon="book"
      title="No knowledge bases"
      description="Create a knowledge base and upload documents to ground your AI."
    />

    <div v-else class="kb__grid">
      <VipCard v-for="kb in data" :key="kb.id" hoverable @click="openDetail(kb)">
        <div class="kb__card-head">
          <span class="kb__card-icon"><VipIcon name="book" :size="16" /></span>
          <VipBadge :tone="STATUS_TONE[kb.status]" variant="soft" size="sm">
            <VipSpinner v-if="kb.status === 'indexing'" :size="10" />{{ kb.status }}
          </VipBadge>
        </div>
        <h3 class="kb__card-name">{{ kb.name }}</h3>
        <div class="kb__card-meta">
          <span><VipIcon name="report" :size="12" /> {{ kb.documents.toLocaleString() }} docs</span>
          <span><VipIcon name="clock" :size="12" /> {{ relativeTime(kb.lastIndexed) }}</span>
        </div>
      </VipCard>
    </div>

    <!-- Detail drawer -->
    <VipDrawer :open="!!selected" :title="selected?.name" :width="560" @close="selected = null">
      <div v-if="selected" class="kb__detail">
        <div class="kb__stats">
          <div class="kb__stat"><span class="kb__stat-v">{{ selected.documents.toLocaleString() }}</span><span class="kb__stat-l">Documents</span></div>
          <div class="kb__stat"><span class="kb__stat-v">{{ selected.status }}</span><span class="kb__stat-l">Status</span></div>
          <div class="kb__stat"><span class="kb__stat-v">{{ relativeTime(selected.lastIndexed) }}</span><span class="kb__stat-l">Last indexed</span></div>
        </div>

        <VipAlert v-if="selected.status === 'error'" tone="danger" title="Indexing failed">
          The last embedding job failed. Reindex to retry, or check the source connection.
        </VipAlert>

        <section class="kb__section">
          <div class="kb__section-head">
            <h4 class="kb__section-title">Documents</h4>
            <VipButton variant="tertiary" size="xs" icon="refresh" @click="reindex">Reindex</VipButton>
          </div>
          <div class="kb__docs">
            <div v-for="d in MOCK_DOCS" :key="d.id" class="kb__doc">
              <VipIcon name="report" :size="14" class="kb__doc-icon" />
              <span class="kb__doc-name">{{ d.name }}</span>
              <span class="kb__doc-pages">{{ d.pages }}p</span>
              <VipBadge :tone="d.status === 'ready' ? 'success' : 'info'" variant="soft" size="sm">{{ d.status }}</VipBadge>
            </div>
          </div>
        </section>

        <section class="kb__section">
          <h4 class="kb__section-title">Chunking &amp; embedding</h4>
          <div class="kb__config">
            <VipInput :model-value="'Recursive · 800 tokens · 120 overlap'" label="Chunking strategy" readonly />
            <VipInput :model-value="'veltrix-embed-3 (1536d)'" label="Embedding model" readonly />
            <VipInput :model-value="'Cosine similarity · top-k 6'" label="Retrieval" readonly />
          </div>
        </section>

        <section class="kb__section">
          <h4 class="kb__section-title">Search test</h4>
          <VipInput
            v-model="searchTest"
            icon="search"
            placeholder="Type a query to preview retrieved chunks"
            @enter="runSearchTest"
          />
          <div v-if="searching" class="kb__loading"><VipSpinner label="Retrieving" /></div>
          <div v-else-if="chunks.length" class="kb__chunks">
            <div v-for="c in chunks" :key="c.id" class="kb__chunk">
              <div class="kb__chunk-head">
                <VipBadge tone="neutral" variant="outline" size="sm">{{ c.doc }}</VipBadge>
                <span class="kb__chunk-score">{{ c.score.toFixed(2) }}</span>
              </div>
              <p class="kb__chunk-text">{{ c.text }}</p>
            </div>
          </div>
        </section>
      </div>
      <template #footer>
        <VipButton variant="tertiary" icon="refresh" @click="reindex">Reindex</VipButton>
        <VipButton variant="secondary" @click="selected = null">Close</VipButton>
      </template>
    </VipDrawer>

    <!-- New KB dialog -->
    <VipDialog :open="createOpen" title="New knowledge base" description="Name the collection, then add documents." @close="createOpen = false">
      <div class="kb__create">
        <VipInput v-model="newName" label="Name" placeholder="e.g. Product Docs" required />
        <div class="kb__drop" :class="{ 'is-over': dragOver }" @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="dragOver = false">
          <VipIcon name="upload" :size="24" />
          <p class="kb__drop-title">Drag &amp; drop documents here</p>
          <p class="kb__drop-note">PDF, DOCX, PPTX, XLSX, TXT · up to 100MB each</p>
        </div>
        <VipAlert tone="info" title="Upload requires a backend">
          Document upload and indexing are handled server-side. This zone is a visual placeholder until the ingestion service is connected.
        </VipAlert>
      </div>
      <template #footer>
        <VipButton variant="secondary" @click="createOpen = false">Cancel</VipButton>
        <VipButton variant="primary" icon="check" @click="createKb">Create</VipButton>
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.kb { max-width: 1280px; margin: 0 auto; }
.kb__loading { display: flex; justify-content: center; padding: var(--vip-sp-9); }
.kb__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--vip-sp-6); }
.kb__card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--vip-sp-5); }
.kb__card-icon { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; border-radius: var(--vip-radius-md); background: var(--vip-brand-soft); color: var(--vip-brand-text); }
.kb__card-name { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-4); }
.kb__card-meta { display: flex; gap: var(--vip-sp-6); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.kb__card-meta span { display: inline-flex; align-items: center; gap: var(--vip-sp-2); }

.kb__detail { display: flex; flex-direction: column; gap: var(--vip-sp-7); }
.kb__stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--vip-sp-5); }
.kb__stat { display: flex; flex-direction: column; gap: 2px; padding: var(--vip-sp-5); background: var(--vip-surface-2); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); }
.kb__stat-v { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); text-transform: capitalize; }
.kb__stat-l { font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); }

.kb__section { display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.kb__section-head { display: flex; align-items: center; justify-content: space-between; }
.kb__section-title { font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-semibold); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); }
.kb__docs { display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.kb__doc { display: flex; align-items: center; gap: var(--vip-sp-4); padding: var(--vip-sp-4) var(--vip-sp-5); background: var(--vip-surface-2); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); }
.kb__doc-icon { color: var(--vip-text-muted); flex: none; }
.kb__doc-name { flex: 1; font-size: var(--vip-fs-sm); color: var(--vip-text-primary); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb__doc-pages { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); font-family: var(--vip-font-mono); }
.kb__config { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.kb__chunks { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.kb__chunk { padding: var(--vip-sp-5); background: var(--vip-surface-2); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); }
.kb__chunk-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--vip-sp-3); }
.kb__chunk-score { font-size: var(--vip-fs-xs); font-family: var(--vip-font-mono); color: var(--vip-success-text); }
.kb__chunk-text { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); line-height: var(--vip-lh-snug); }

.kb__create { display: flex; flex-direction: column; gap: var(--vip-sp-6); }
.kb__drop { display: flex; flex-direction: column; align-items: center; gap: var(--vip-sp-3); padding: var(--vip-sp-10) var(--vip-sp-7); border: 1.5px dashed var(--vip-border-strong); border-radius: var(--vip-radius-lg); color: var(--vip-text-muted); text-align: center; transition: border-color var(--vip-motion-fast), background var(--vip-motion-fast); }
.kb__drop.is-over { border-color: var(--vip-brand-500); background: var(--vip-brand-soft); }
.kb__drop-title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.kb__drop-note { font-size: var(--vip-fs-xs); }
</style>
