<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PipelineEditor } from './usePipelineEditor'
import type { NodeConfigField } from '@/shared/types/pipeline'
import { NODE_TYPES } from './nodeTypes'
import VipInput from '@/shared/ui/VipInput.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import FormulaEditor from './FormulaEditor.vue'
import SourceConfigurationPanel from './SourceConfigurationPanel.vue'

const props = defineProps<{ editor: PipelineEditor }>()

const tab = ref<'config' | 'schema' | 'docs'>('config')
const node = props.editor.selectedNode
const spec = computed(() => (node.value ? NODE_TYPES[node.value.kind] : null))
const issues = computed(() => (node.value ? (props.editor.nodeIssues.value.get(node.value.id) ?? []) : []))

const visibleFields = computed<NodeConfigField[]>(() => {
  if (!spec.value || !node.value) return []
  return spec.value.config.filter((f) => {
    if (!f.visibleWhen) return true
    return node.value!.config[f.visibleWhen.key] === f.visibleWhen.equals
  })
})

function val(key: string): unknown {
  return node.value?.config[key]
}
function set(key: string, value: unknown) {
  if (node.value) props.editor.updateNodeConfig(node.value.id, key, value)
}

/* key-value editor local rows */
const kvRows = ref<Record<string, { k: string; v: string }[]>>({})
watch(
  node,
  () => {
    kvRows.value = {}
    visibleFields.value.forEach((f) => {
      if (f.type === 'keyvalue') {
        const obj = (val(f.key) as Record<string, string>) ?? {}
        kvRows.value[f.key] = Object.entries(obj).map(([k, v]) => ({ k, v: String(v) }))
        if (!kvRows.value[f.key].length) kvRows.value[f.key] = [{ k: '', v: '' }]
      }
    })
  },
  { immediate: true },
)
function commitKv(key: string) {
  const obj: Record<string, string> = {}
  kvRows.value[key].forEach((r) => {
    if (r.k) obj[r.k] = r.v
  })
  set(key, obj)
}

const titleModel = computed({
  get: () => node.value?.title ?? '',
  set: (v: string) => node.value && props.editor.renameNode(node.value.id, v),
})

const columnsModel = (key: string) => ({
  get: () => ((val(key) as string[]) ?? []).join(', '),
  set: (v: string) =>
    set(
      key,
      v
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    ),
})
</script>

<template>
  <aside class="insp">
    <div v-if="!node" class="insp__empty">
      <VipEmptyState
        icon="settings"
        title="No node selected"
        description="Select a node on the canvas to configure it."
      />
    </div>

    <template v-else>
      <header class="insp__head">
        <span class="insp__icon" :class="`is-${spec!.category}`"><VipIcon :name="spec!.icon" :size="16" /></span>
        <div class="insp__titles">
          <input v-model="titleModel" class="insp__name" aria-label="Node name" />
          <span class="insp__kind">{{ spec!.label }}</span>
        </div>
      </header>

      <div v-if="issues.length" class="insp__issues">
        <div v-for="i in issues" :key="i.id" class="insp__issue" :class="`is-${i.level}`">
          <VipIcon :name="i.level === 'error' ? 'error' : 'warning'" :size="13" />
          {{ i.message }}
        </div>
      </div>

      <div class="insp__tabs">
        <VipSegmented
          :model-value="tab"
          :options="[
            { value: 'config', label: 'Config' },
            { value: 'schema', label: 'Schema' },
            { value: 'docs', label: 'Docs' },
          ]"
          size="sm"
          @update:model-value="tab = $event as typeof tab"
        />
      </div>

      <div class="insp__body">
        <!-- CONFIG -->
        <div v-if="tab === 'config'" class="insp__fields">
          <SourceConfigurationPanel v-if="node.kind === 'source-dataset'" :editor="editor" :node="node" />
          <template v-for="f in visibleFields" :key="f.key">
            <VipInput
              v-if="f.type === 'text'"
              :label="f.label"
              :model-value="(val(f.key) as string) ?? ''"
              :placeholder="f.placeholder"
              :required="f.required"
              :help="f.help"
              @update:model-value="set(f.key, $event)"
            />
            <VipInput
              v-else-if="f.type === 'number'"
              type="number"
              :label="f.label"
              :model-value="(val(f.key) as number) ?? 0"
              :required="f.required"
              :help="f.help"
              @update:model-value="set(f.key, $event)"
            />
            <VipInput
              v-else-if="f.type === 'secret'"
              type="password"
              :label="f.label"
              :model-value="(val(f.key) as string) ?? ''"
              :required="f.required"
              help="Secrets are resolved from the connection vault at run time — never stored in the pipeline."
              @update:model-value="set(f.key, $event)"
            />
            <VipTextarea
              v-else-if="f.type === 'textarea'"
              :label="f.label"
              :model-value="(val(f.key) as string) ?? ''"
              :placeholder="f.placeholder"
              :required="f.required"
              :help="f.help"
              @update:model-value="set(f.key, $event)"
            />
            <VipTextarea
              v-else-if="f.type === 'code'"
              mono
              :rows="6"
              :label="`${f.label}${f.language ? ` (${f.language.toUpperCase()})` : ''}`"
              :model-value="(val(f.key) as string) ?? ''"
              :placeholder="f.placeholder"
              :required="f.required"
              :help="f.help"
              @update:model-value="set(f.key, $event)"
            />
            <FormulaEditor
              v-else-if="f.type === 'formula'"
              :label="f.label"
              :model-value="(val(f.key) as string) ?? ''"
              :columns="node.outputSchema"
              @update:model-value="set(f.key, $event)"
            />
            <VipSelect
              v-else-if="f.type === 'select'"
              :label="f.label"
              :model-value="(val(f.key) as string) ?? ''"
              :options="f.options ?? []"
              :required="f.required"
              :help="f.help"
              placeholder="Select…"
              @update:model-value="set(f.key, $event)"
            />
            <VipInput
              v-else-if="f.type === 'columns'"
              :label="f.label"
              :model-value="columnsModel(f.key).get()"
              placeholder="col_a, col_b"
              :help="f.help ?? 'Comma-separated column names.'"
              @update:model-value="columnsModel(f.key).set($event as string)"
            />

            <div v-else-if="f.type === 'boolean'" class="insp__bool">
              <VipSwitch :model-value="!!val(f.key)" :label="f.label" @update:model-value="set(f.key, $event)" />
              <p v-if="f.help" class="insp__help">{{ f.help }}</p>
            </div>

            <div v-else-if="f.type === 'keyvalue'" class="insp__kv">
              <label class="insp__kv-label">{{ f.label }}<span v-if="f.required" class="insp__req">*</span></label>
              <div v-for="(row, ri) in kvRows[f.key]" :key="ri" class="insp__kv-row">
                <input v-model="row.k" class="insp__kv-input" placeholder="key" @change="commitKv(f.key)" />
                <span class="insp__kv-arrow">→</span>
                <input v-model="row.v" class="insp__kv-input" placeholder="value" @change="commitKv(f.key)" />
                <button
                  class="insp__kv-del"
                  aria-label="Remove"
                  @click="(kvRows[f.key].splice(ri, 1), commitKv(f.key))"
                >
                  <VipIcon name="close" :size="12" />
                </button>
              </div>
              <button class="insp__kv-add" @click="kvRows[f.key].push({ k: '', v: '' })">
                <VipIcon name="plus" :size="12" /> Add
              </button>
              <p v-if="f.help" class="insp__help">{{ f.help }}</p>
            </div>
          </template>
        </div>

        <!-- SCHEMA -->
        <div v-else-if="tab === 'schema'" class="insp__schema">
          <div class="insp__schema-title">Output schema</div>
          <table class="insp__schema-table">
            <tbody>
              <tr v-for="col in node.outputSchema ?? []" :key="col.name">
                <td class="insp__col-name">{{ col.name }}</td>
                <td>
                  <VipBadge tone="neutral" size="sm">{{ col.dataType }}</VipBadge>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!node.outputSchema?.length" class="insp__help">Schema is inferred after a successful run.</p>
        </div>

        <!-- DOCS -->
        <div v-else class="insp__docs">
          <p class="insp__docs-text">{{ spec!.docs }}</p>
          <div class="insp__docs-io">
            <div>
              <span class="insp__docs-lbl">Inputs</span> {{ spec!.inputs.map((i) => i.label).join(', ') || 'None' }}
            </div>
            <div>
              <span class="insp__docs-lbl">Outputs</span> {{ spec!.outputs.map((o) => o.label).join(', ') || 'None' }}
            </div>
          </div>
        </div>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.insp {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--vip-surface-1);
}
.insp__empty {
  flex: 1;
  display: flex;
  align-items: center;
}
.insp__head {
  display: flex;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.insp__icon {
  width: 32px;
  height: 32px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.insp__icon.is-source {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.insp__icon.is-transform {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.insp__icon.is-output {
  background: var(--vip-warning-soft);
  color: var(--vip-warning-text);
}
.insp__titles {
  min-width: 0;
  flex: 1;
}
.insp__name {
  width: 100%;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-sm);
  padding: 2px 4px;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.insp__name:hover {
  border-color: var(--vip-border);
}
.insp__name:focus {
  border-color: var(--vip-brand-500);
  outline: none;
}
.insp__kind {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  padding: 0 4px;
}

.insp__issues {
  padding: var(--vip-sp-4) var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.insp__issue {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-xs);
}
.insp__issue.is-error {
  color: var(--vip-danger-text);
}
.insp__issue.is-warning {
  color: var(--vip-warning-text);
}

.insp__tabs {
  padding: var(--vip-sp-5) var(--vip-sp-6) 0;
}
.insp__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--vip-sp-6);
}
.insp__fields {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.insp__bool {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.insp__help {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.insp__req {
  color: var(--vip-danger);
  margin-left: 3px;
}

.insp__kv {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.insp__kv-label {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
}
.insp__kv-row {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.insp__kv-input {
  flex: 1;
  min-width: 0;
  height: 30px;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  padding: 0 var(--vip-sp-4);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-sm);
  outline: none;
}
.insp__kv-input:focus {
  border-color: var(--vip-brand-500);
}
.insp__kv-arrow {
  color: var(--vip-text-disabled);
}
.insp__kv-del {
  width: 24px;
  height: 24px;
  flex: none;
  background: none;
  border: none;
  color: var(--vip-text-muted);
  border-radius: var(--vip-radius-sm);
}
.insp__kv-del:hover {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.insp__kv-add {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  background: none;
  border: 1px dashed var(--vip-border-strong);
  border-radius: var(--vip-radius-sm);
  padding: var(--vip-sp-2) var(--vip-sp-4);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-xs);
}
.insp__kv-add:hover {
  border-color: var(--vip-brand-500);
  color: var(--vip-brand-text);
}

.insp__schema-title {
  font-size: var(--vip-fs-xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
  margin-bottom: var(--vip-sp-4);
}
.insp__schema-table {
  width: 100%;
  border-collapse: collapse;
}
.insp__schema-table td {
  padding: var(--vip-sp-3) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
  font-size: var(--vip-fs-sm);
}
.insp__col-name {
  font-family: var(--vip-font-mono);
  color: var(--vip-text-secondary);
}

.insp__docs-text {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  line-height: var(--vip-lh-normal);
}
.insp__docs-io {
  margin-top: var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.insp__docs-lbl {
  display: inline-block;
  width: 64px;
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
  text-transform: uppercase;
}
</style>
