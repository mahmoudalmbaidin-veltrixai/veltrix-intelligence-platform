<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useMutation } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { semanticStudioService, type GlossaryTerm, type GlossaryStatus } from './semantic.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const ui = useUiStore()
const platform = usePlatformStore()
const canWrite = computed(() => platform.can('semantic:write'))

const { data, isLoading, refetch } = useQuery(
  () => 'semantic:glossary',
  () => semanticStudioService.listTerms(),
)

const search = ref('')
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  const terms = data.value ?? []
  if (!q) return terms
  return terms.filter(
    (t) =>
      t.term.toLowerCase().includes(q) ||
      t.definition.toLowerCase().includes(q) ||
      t.synonyms.some((s) => s.toLowerCase().includes(q)),
  )
})

const selectedId = ref<string | null>(null)
const selected = computed(() => (data.value ?? []).find((t) => t.id === selectedId.value) ?? null)

watch(filtered, (list) => {
  if (!list.some((t) => t.id === selectedId.value)) selectedId.value = list[0]?.id ?? null
}, { immediate: true })

const statusTone: Record<GlossaryStatus, 'success' | 'warning' | 'neutral'> = {
  approved: 'success', draft: 'warning', deprecated: 'neutral',
}

/* ---- create dialog ---- */
const dialogOpen = ref(false)
interface Draft { term: string; definition: string; owner: string; steward: string; synonyms: string }
const draft = reactive<Draft>({ term: '', definition: '', owner: '', steward: '', synonyms: '' })

function openDialog() {
  draft.term = ''
  draft.definition = ''
  draft.owner = platform.user.name
  draft.steward = platform.user.name
  draft.synonyms = ''
  dialogOpen.value = true
}

const termError = computed(() => (draft.term.trim().length === 0 ? 'Term is required' : ''))
const canSubmit = computed(() => !termError.value && draft.definition.trim().length > 0)

const { mutate, isPending } = useMutation(
  (input: Omit<GlossaryTerm, 'id'>) => semanticStudioService.createTerm(input),
  {
    invalidate: ['semantic:glossary'],
    onSuccess: (t) => {
      ui.pushToast({ kind: 'success', title: 'Term added', message: `${t.term} added as ${t.status}.` })
      dialogOpen.value = false
      refetch().then(() => (selectedId.value = t.id))
    },
  },
)

async function submit() {
  if (!canSubmit.value) return
  await mutate({
    term: draft.term.trim(),
    definition: draft.definition.trim(),
    owner: draft.owner.trim() || platform.user.name,
    steward: draft.steward.trim() || platform.user.name,
    status: 'draft',
    synonyms: draft.synonyms.split(',').map((s) => s.trim()).filter(Boolean),
    relatedTerms: [],
    linkedDatasets: [],
  })
}
</script>

<template>
  <div class="wrap">
    <VipPageHeader title="Business glossary" description="Shared, governed definitions of business terms with owners, stewards and approval state.">
      <template #actions>
        <VipButton variant="primary" icon="plus" :disabled="!canWrite" @click="openDialog">New term</VipButton>
      </template>
    </VipPageHeader>

    <div class="layout">
      <aside class="list">
        <div class="list__search">
          <VipInput v-model="search" icon="search" placeholder="Search terms…" size="sm" />
        </div>
        <div v-if="isLoading" class="list__body">
          <div v-for="n in 6" :key="n" class="list__sk"><VipSkeleton width="70%" /><VipSkeleton width="40%" height="10px" style="margin-top:6px" /></div>
        </div>
        <div v-else-if="filtered.length === 0" class="list__empty">
          <VipEmptyState icon="search" title="No matches" description="Try a different search term." />
        </div>
        <div v-else class="list__body">
          <button
            v-for="t in filtered"
            :key="t.id"
            type="button"
            class="term"
            :class="{ 'is-active': t.id === selectedId }"
            @click="selectedId = t.id"
          >
            <div class="term__row">
              <span class="term__name">{{ t.term }}</span>
              <VipBadge :tone="statusTone[t.status]" variant="dot" size="sm">{{ t.status }}</VipBadge>
            </div>
            <div class="term__def">{{ t.definition }}</div>
          </button>
        </div>
      </aside>

      <section class="detail">
        <template v-if="selected">
          <header class="detail__head">
            <div>
              <h2 class="detail__title">{{ selected.term }}</h2>
              <div class="detail__syn" v-if="selected.synonyms.length">
                <span v-for="s in selected.synonyms" :key="s" class="chip">{{ s }}</span>
              </div>
            </div>
            <VipBadge :tone="statusTone[selected.status]" variant="soft">{{ selected.status }}</VipBadge>
          </header>

          <p class="detail__def">{{ selected.definition }}</p>

          <div class="detail__grid">
            <div class="kv"><span class="kv__k"><VipIcon name="users" :size="13" /> Owner</span><span class="kv__v">{{ selected.owner }}</span></div>
            <div class="kv"><span class="kv__k"><VipIcon name="shield" :size="13" /> Steward</span><span class="kv__v">{{ selected.steward }}</span></div>
          </div>

          <div v-if="selected.relatedTerms.length" class="block">
            <div class="block__title">Related terms</div>
            <div class="chips">
              <span v-for="r in selected.relatedTerms" :key="r" class="chip chip--link"><VipIcon name="link" :size="11" /> {{ r }}</span>
            </div>
          </div>

          <div v-if="selected.linkedDatasets.length" class="block">
            <div class="block__title">Linked datasets</div>
            <div class="chips">
              <span v-for="d in selected.linkedDatasets" :key="d" class="chip chip--data"><VipIcon name="database" :size="11" /> {{ d }}</span>
            </div>
          </div>
        </template>
        <VipEmptyState v-else icon="book" title="Select a term" description="Choose a glossary term to view its definition and governance." />
      </section>
    </div>

    <VipDialog :open="dialogOpen" title="New glossary term" description="Terms are created as drafts and require a steward's approval." @close="dialogOpen = false">
      <div class="form">
        <VipInput v-model="draft.term" label="Term" placeholder="e.g. Net Revenue Retention" required :error="draft.term ? termError : ''" />
        <VipTextarea v-model="draft.definition" label="Definition" :rows="3" placeholder="A precise, unambiguous definition." required />
        <div class="row2">
          <VipInput v-model="draft.owner" label="Owner" placeholder="Team or person" />
          <VipInput v-model="draft.steward" label="Steward" placeholder="Approver" />
        </div>
        <VipInput v-model="draft.synonyms" label="Synonyms" placeholder="Comma separated" help="Alternate names people use for this term." />
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="dialogOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="isPending" :disabled="!canSubmit" @click="submit">Add term</VipButton>
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.wrap { max-width: 1180px; }
.layout { display: grid; grid-template-columns: 340px 1fr; gap: var(--vip-sp-6); align-items: start; }

.list { background: var(--vip-surface-1); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-lg); overflow: hidden; }
.list__search { padding: var(--vip-sp-5); border-bottom: 1px solid var(--vip-border-subtle); }
.list__body { max-height: 620px; overflow-y: auto; padding: var(--vip-sp-3); }
.list__sk { padding: var(--vip-sp-4) var(--vip-sp-5); }
.list__empty { padding: var(--vip-sp-6); }
.term { display: block; width: 100%; text-align: left; padding: var(--vip-sp-4) var(--vip-sp-5); background: none; border: none; border-radius: var(--vip-radius-md); cursor: pointer; }
.term:hover { background: var(--vip-surface-hover); }
.term.is-active { background: var(--vip-brand-soft); }
.term__row { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-4); }
.term__name { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.term__def { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }

.detail { background: var(--vip-surface-1); border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-lg); padding: var(--vip-sp-8); min-height: 320px; }
.detail__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--vip-sp-6); }
.detail__title { font-size: var(--vip-fs-2xl); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); }
.detail__syn { display: flex; flex-wrap: wrap; gap: var(--vip-sp-3); margin-top: var(--vip-sp-4); }
.detail__def { font-size: var(--vip-fs-md); color: var(--vip-text-secondary); line-height: var(--vip-lh-normal); margin-top: var(--vip-sp-6); max-width: 640px; }
.detail__grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-5); margin-top: var(--vip-sp-7); max-width: 520px; }
.kv { display: flex; flex-direction: column; gap: var(--vip-sp-2); padding: var(--vip-sp-5); background: var(--vip-surface-2); border-radius: var(--vip-radius-md); }
.kv__k { display: inline-flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.kv__v { font-size: var(--vip-fs-md); color: var(--vip-text-primary); font-weight: var(--vip-fw-medium); }
.block { margin-top: var(--vip-sp-7); }
.block__title { font-size: var(--vip-fs-xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-muted); margin-bottom: var(--vip-sp-4); }
.chips { display: flex; flex-wrap: wrap; gap: var(--vip-sp-3); }
.chip { display: inline-flex; align-items: center; gap: var(--vip-sp-2); padding: 3px 9px; font-size: var(--vip-fs-xs); border-radius: var(--vip-radius-full); background: var(--vip-surface-3); color: var(--vip-text-secondary); }
.chip--link { background: var(--vip-brand-soft); color: var(--vip-brand-text); }
.chip--data { background: var(--vip-info-soft); color: var(--vip-info-text); }

.form { display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-5); }
</style>
