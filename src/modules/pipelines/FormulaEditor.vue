<script setup lang="ts">
import { ref, computed } from 'vue'
import { FORMULA_FUNCTIONS, validateFormula, type FormulaFn } from './formulaFunctions'
import type { SchemaColumn } from '@/shared/types/pipeline'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const props = defineProps<{ modelValue: string; columns?: SchemaColumn[]; label?: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const search = ref('')
const activeCat = ref<'All' | FormulaFn['category']>('All')
const taRef = ref<HTMLTextAreaElement>()

const categories: ('All' | FormulaFn['category'])[] = ['All', 'Aggregate', 'Math', 'Text', 'Logical', 'Date', 'Conversion']

const fns = computed(() => {
  const q = search.value.trim().toLowerCase()
  return FORMULA_FUNCTIONS.filter(
    (f) =>
      (activeCat.value === 'All' || f.category === activeCat.value) &&
      (!q || f.name.toLowerCase().includes(q) || f.description.toLowerCase().includes(q)),
  )
})

const validation = computed(() => validateFormula(props.modelValue))

function insertAtCursor(text: string) {
  const ta = taRef.value
  const cur = props.modelValue ?? ''
  if (!ta) { emit('update:modelValue', cur + text); return }
  const start = ta.selectionStart ?? cur.length
  const end = ta.selectionEnd ?? cur.length
  const next = cur.slice(0, start) + text + cur.slice(end)
  emit('update:modelValue', next)
  requestAnimationFrame(() => {
    ta.focus()
    const pos = start + text.length
    ta.setSelectionRange(pos, pos)
  })
}
function insertFn(fn: FormulaFn) {
  // insert NAME( with caret inside the parens
  insertAtCursor(`${fn.name}()`)
  const ta = taRef.value
  if (ta) requestAnimationFrame(() => { const p = (ta.selectionStart ?? 1) - 1; ta.setSelectionRange(p, p) })
}
function insertColumn(name: string) {
  insertAtCursor(`[${name}]`)
}
</script>

<template>
  <div class="fx">
    <label v-if="label" class="fx__label">{{ label }}</label>
    <div class="fx__editor">
      <textarea
        ref="taRef"
        class="fx__input"
        :value="modelValue"
        rows="4"
        spellcheck="false"
        placeholder="e.g. IF([revenue] > 0, ROUND([profit] / [revenue], 2), 0)"
        aria-label="Formula expression"
        @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
      />
      <div class="fx__status" :class="validation.valid ? 'is-ok' : 'is-err'">
        <VipIcon :name="validation.valid ? 'success' : 'error'" :size="13" />
        <span v-if="validation.valid">Valid · {{ validation.usedFunctions.length }} function(s), {{ validation.usedColumns.length }} column(s)</span>
        <span v-else>{{ validation.errors[0] }}</span>
      </div>
    </div>

    <div v-if="columns && columns.length" class="fx__columns">
      <span class="fx__section">Columns</span>
      <button v-for="c in columns" :key="c.name" class="fx__col" @click="insertColumn(c.name)">
        <VipIcon name="hash" :size="11" />{{ c.name }}
      </button>
    </div>

    <div class="fx__catalog">
      <div class="fx__toolbar">
        <VipInput v-model="search" icon="search" placeholder="Search functions…" size="sm" />
        <div class="fx__cats">
          <button
            v-for="c in categories"
            :key="c"
            class="fx__cat"
            :class="{ 'is-active': activeCat === c }"
            @click="activeCat = c"
          >{{ c }}</button>
        </div>
      </div>
      <div class="fx__list">
        <div v-for="fn in fns" :key="fn.name" class="fx__fn" @click="insertFn(fn)">
          <div class="fx__fn-top">
            <code class="fx__fn-name">{{ fn.signature }}</code>
            <VipBadge tone="neutral" size="sm">{{ fn.category }}</VipBadge>
          </div>
          <div class="fx__fn-desc">{{ fn.description }}</div>
          <code class="fx__fn-ex">{{ fn.example }}</code>
        </div>
        <div v-if="!fns.length" class="fx__empty">No functions match “{{ search }}”.</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fx { display: flex; flex-direction: column; gap: var(--vip-sp-4); }
.fx__label { font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-medium); color: var(--vip-text-secondary); }
.fx__editor { border: 1px solid var(--vip-border); border-radius: var(--vip-radius-md); overflow: hidden; background: var(--vip-surface-2); }
.fx__editor:focus-within { border-color: var(--vip-brand-500); box-shadow: 0 0 0 3px var(--vip-brand-soft); }
.fx__input { width: 100%; border: none; background: none; outline: none; resize: vertical; padding: var(--vip-sp-4); color: var(--vip-text-primary); font-family: var(--vip-font-mono); font-size: var(--vip-fs-sm); line-height: 1.5; }
.fx__status { display: flex; align-items: center; gap: var(--vip-sp-2); padding: var(--vip-sp-2) var(--vip-sp-4); font-size: var(--vip-fs-2xs); border-top: 1px solid var(--vip-border-subtle); }
.fx__status.is-ok { color: var(--vip-success-text); }
.fx__status.is-err { color: var(--vip-danger-text); }

.fx__columns { display: flex; flex-wrap: wrap; align-items: center; gap: var(--vip-sp-2); }
.fx__section { font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-disabled); margin-right: var(--vip-sp-2); }
.fx__col { display: inline-flex; align-items: center; gap: 2px; padding: 2px 7px; background: var(--vip-surface-3); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-full); color: var(--vip-text-secondary); font-family: var(--vip-font-mono); font-size: var(--vip-fs-2xs); }
.fx__col:hover { border-color: var(--vip-brand-500); color: var(--vip-brand-text); }

.fx__catalog { border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); overflow: hidden; }
.fx__toolbar { padding: var(--vip-sp-4); border-bottom: 1px solid var(--vip-border-subtle); display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.fx__cats { display: flex; flex-wrap: wrap; gap: var(--vip-sp-2); }
.fx__cat { padding: 2px 8px; background: none; border: 1px solid var(--vip-border); border-radius: var(--vip-radius-full); color: var(--vip-text-muted); font-size: var(--vip-fs-2xs); }
.fx__cat.is-active { background: var(--vip-brand-soft); border-color: var(--vip-brand-500); color: var(--vip-brand-text); }
.fx__list { max-height: 240px; overflow-y: auto; padding: var(--vip-sp-3); }
.fx__fn { padding: var(--vip-sp-3) var(--vip-sp-4); border-radius: var(--vip-radius-sm); cursor: pointer; }
.fx__fn:hover { background: var(--vip-surface-hover); }
.fx__fn-top { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-3); }
.fx__fn-name { font-family: var(--vip-font-mono); font-size: var(--vip-fs-xs); color: var(--vip-brand-text); }
.fx__fn-desc { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: 2px; }
.fx__fn-ex { font-family: var(--vip-font-mono); font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); }
.fx__empty { padding: var(--vip-sp-6); text-align: center; color: var(--vip-text-muted); font-size: var(--vip-fs-sm); }
</style>
