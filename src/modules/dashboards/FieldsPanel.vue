<script setup lang="ts">
import { ref, computed } from 'vue'
import { MODELS } from '@/shared/services/semanticModels'
import type { SemanticField } from '@/shared/types/semantic'
import { WIDGET_CATALOG } from './widgetFactory'
import type { WidgetType } from '@/shared/types/dashboard'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'

const props = defineProps<{ modelId: string }>()
const emit = defineEmits<{ addWidget: [WidgetType]; 'update:modelId': [string] }>()

const mode = ref<'visuals' | 'fields'>('visuals')
const search = ref('')

const model = computed(() => MODELS.find((m) => m.id === props.modelId) ?? MODELS[0])
const folders = computed(() => {
  const q = search.value.trim().toLowerCase()
  const map = new Map<string, SemanticField[]>()
  model.value.fields
    .filter((f) => !q || f.label.toLowerCase().includes(q))
    .forEach((f) => {
      const folder = f.folder ?? 'Fields'
      if (!map.has(folder)) map.set(folder, [])
      map.get(folder)!.push(f)
    })
  return [...map.entries()]
})

const catalogGroups = computed(() => {
  const map = new Map<string, typeof WIDGET_CATALOG>()
  WIDGET_CATALOG.forEach((c) => {
    if (!map.has(c.group)) map.set(c.group, [])
    map.get(c.group)!.push(c)
  })
  return [...map.entries()]
})

function roleIcon(role: SemanticField['role']): string {
  return role === 'measure' ? 'hash' : role === 'metric' ? 'target' : role === 'time' ? 'calendar' : 'text'
}
function onFieldDrag(e: DragEvent, f: SemanticField) {
  e.dataTransfer?.setData('application/vip-field', f.id)
}
function onWidgetDrag(e: DragEvent, t: WidgetType) {
  e.dataTransfer?.setData('application/vip-widget', t)
}
</script>

<template>
  <aside class="fpanel">
    <div class="fpanel__mode">
      <VipSegmented
        v-model="mode"
        :options="[{ value: 'visuals', label: 'Visuals', icon: 'chart' }, { value: 'fields', label: 'Data', icon: 'database' }]"
        size="sm"
      />
    </div>

    <!-- VISUALS -->
    <div v-if="mode === 'visuals'" class="fpanel__scroll">
      <div v-for="[group, items] in catalogGroups" :key="group" class="fpanel__group">
        <div class="fpanel__group-label">{{ group }}</div>
        <div class="fpanel__viz-grid">
          <button
            v-for="c in items"
            :key="c.type"
            class="fpanel__viz"
            :title="c.label"
            draggable="true"
            @dragstart="onWidgetDrag($event, c.type)"
            @click="emit('addWidget', c.type)"
          >
            <VipIcon :name="c.icon" :size="18" />
            <span>{{ c.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- FIELDS -->
    <div v-else class="fpanel__scroll">
      <div class="fpanel__model">
        <VipSelect
          :model-value="modelId"
          :options="MODELS.map((m) => ({ value: m.id, label: m.label }))"
          size="sm"
          @update:model-value="emit('update:modelId', $event)"
        />
      </div>
      <div class="fpanel__search">
        <VipInput v-model="search" icon="search" placeholder="Search fields…" size="sm" />
      </div>
      <div v-for="[folder, fields] in folders" :key="folder" class="fpanel__group">
        <div class="fpanel__group-label"><VipIcon name="folder" :size="12" /> {{ folder }}</div>
        <div
          v-for="f in fields"
          :key="f.id"
          class="fpanel__field"
          :class="`is-${f.role}`"
          draggable="true"
          @dragstart="onFieldDrag($event, f)"
        >
          <VipIcon :name="roleIcon(f.role)" :size="13" />
          <span class="fpanel__field-name">{{ f.label }}</span>
          <VipIcon v-if="f.sensitive" name="lock" :size="11" class="fpanel__sensitive" />
        </div>
      </div>
    </div>
    <div class="fpanel__hint">Drag onto the canvas or a field well</div>
  </aside>
</template>

<style scoped>
.fpanel { display: flex; flex-direction: column; height: 100%; background: var(--vip-surface-1); }
.fpanel__mode { padding: var(--vip-sp-5); border-bottom: 1px solid var(--vip-border-subtle); }
.fpanel__mode :deep(.vip-seg) { width: 100%; }
.fpanel__mode :deep(.vip-seg__btn) { flex: 1; justify-content: center; }
.fpanel__scroll { flex: 1; overflow-y: auto; padding: var(--vip-sp-5); }
.fpanel__model, .fpanel__search { margin-bottom: var(--vip-sp-5); }
.fpanel__group { margin-bottom: var(--vip-sp-6); }
.fpanel__group-label { display: flex; align-items: center; gap: var(--vip-sp-2); font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-disabled); margin-bottom: var(--vip-sp-3); }
.fpanel__viz-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-3); }
.fpanel__viz {
  display: flex; flex-direction: column; align-items: center; gap: var(--vip-sp-2);
  padding: var(--vip-sp-4) var(--vip-sp-2); background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary); font-size: var(--vip-fs-2xs); text-align: center; cursor: grab;
}
.fpanel__viz:hover { border-color: var(--vip-brand-500); color: var(--vip-brand-text); background: var(--vip-brand-soft); }
.fpanel__field {
  display: flex; align-items: center; gap: var(--vip-sp-3);
  padding: var(--vip-sp-3) var(--vip-sp-4); border-radius: var(--vip-radius-sm);
  color: var(--vip-text-secondary); font-size: var(--vip-fs-sm); cursor: grab;
}
.fpanel__field:hover { background: var(--vip-surface-hover); }
.fpanel__field.is-measure, .fpanel__field.is-metric { color: var(--vip-brand-text); }
.fpanel__field-name { flex: 1; }
.fpanel__sensitive { color: var(--vip-warning-text); }
.fpanel__hint { padding: var(--vip-sp-4); border-top: 1px solid var(--vip-border-subtle); font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); text-align: center; }
</style>
