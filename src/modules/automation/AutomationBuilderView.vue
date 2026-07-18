<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ACTION_CATALOG, TRIGGER_META, type TriggerType } from './automation.service'
import { useUiStore } from '@/shared/stores/ui'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'

const router = useRouter()
const ui = useUiStore()

const name = ref('New automation')
const trigger = ref<TriggerType>('schedule')
const condition = ref("severity == 'high'")
interface Action {
  id: string
  type: string
  label: string
  icon: string
}
const actions = ref<Action[]>([{ id: 'a1', type: 'notify', label: 'Send notification', icon: 'bell' }])
const selected = ref<string>('trigger')

const triggerOptions = (Object.keys(TRIGGER_META) as TriggerType[]).map((t) => ({
  value: t,
  label: TRIGGER_META[t].label,
}))
const actionMenu = ACTION_CATALOG.map((a) => ({ key: a.type, label: a.label, icon: a.icon }))

function addAction(type: string) {
  const meta = ACTION_CATALOG.find((a) => a.type === type)!
  actions.value.push({ id: `a_${Date.now().toString(36)}`, type, label: meta.label, icon: meta.icon })
}
function removeAction(id: string) {
  actions.value = actions.value.filter((a) => a.id !== id)
}
function move(id: string, dir: -1 | 1) {
  const i = actions.value.findIndex((a) => a.id === id)
  const j = i + dir
  if (j < 0 || j >= actions.value.length) return
  const arr = actions.value
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
}
function validate() {
  if (!actions.value.length) ui.pushToast({ kind: 'warning', title: 'Validation', message: 'Add at least one action.' })
  else
    ui.pushToast({
      kind: 'success',
      title: 'Validation passed',
      message: `Trigger + ${actions.value.length} action(s) configured.`,
    })
}
function publish() {
  ui.pushToast({ kind: 'success', title: 'Automation published', message: `"${name.value}" is now active.` })
}

const selectedTitle = computed(() =>
  selected.value === 'trigger'
    ? 'Trigger'
    : selected.value === 'condition'
      ? 'Condition'
      : (actions.value.find((a) => a.id === selected.value)?.label ?? 'Step'),
)
</script>

<template>
  <div class="abuilder">
    <header class="abuilder__toolbar">
      <div class="abuilder__tb-left">
        <VipButton variant="ghost" size="sm" icon="chevronLeft" @click="router.push('/automation')" />
        <input v-model="name" class="abuilder__name" aria-label="Automation name" />
        <VipBadge tone="neutral" size="sm">draft</VipBadge>
      </div>
      <div class="abuilder__tb-right">
        <VipButton variant="secondary" size="sm" icon="check" @click="validate">Validate</VipButton>
        <VipButton
          variant="secondary"
          size="sm"
          icon="play"
          @click="ui.pushToast({ kind: 'info', title: 'Test run', message: 'Dry-run executed against sample event.' })"
          >Test</VipButton
        >
        <VipButton variant="primary" size="sm" icon="upload" @click="publish">Publish</VipButton>
      </div>
    </header>

    <div class="abuilder__body">
      <div class="abuilder__flow">
        <!-- trigger -->
        <div
          class="aflow__block is-trigger"
          :class="{ 'is-selected': selected === 'trigger' }"
          @click="selected = 'trigger'"
        >
          <div class="aflow__block-head"><VipIcon :name="TRIGGER_META[trigger].icon" :size="15" /> When</div>
          <div class="aflow__block-body">{{ TRIGGER_META[trigger].label }}</div>
        </div>
        <div class="aflow__connector" />
        <!-- condition -->
        <div
          class="aflow__block is-condition"
          :class="{ 'is-selected': selected === 'condition' }"
          @click="selected = 'condition'"
        >
          <div class="aflow__block-head"><VipIcon name="filter" :size="15" /> If</div>
          <div class="aflow__block-body vip-mono">{{ condition || 'always' }}</div>
        </div>
        <div class="aflow__connector" />
        <!-- actions -->
        <div v-for="(a, i) in actions" :key="a.id" class="aflow__wrap">
          <div class="aflow__block is-action" :class="{ 'is-selected': selected === a.id }" @click="selected = a.id">
            <div class="aflow__block-head"><VipIcon :name="a.icon" :size="15" /> Then</div>
            <div class="aflow__block-body">{{ a.label }}</div>
            <div class="aflow__block-actions" @click.stop>
              <button :disabled="i === 0" @click="move(a.id, -1)"><VipIcon name="chevronUp" :size="13" /></button>
              <button :disabled="i === actions.length - 1" @click="move(a.id, 1)">
                <VipIcon name="chevronDown" :size="13" />
              </button>
              <button @click="removeAction(a.id)"><VipIcon name="trash" :size="13" /></button>
            </div>
          </div>
          <div class="aflow__connector" />
        </div>
        <VipMenu :items="actionMenu" align="start" @select="addAction">
          <template #trigger
            ><button class="aflow__add"><VipIcon name="plus" :size="15" /> Add action</button></template
          >
        </VipMenu>
      </div>

      <aside class="abuilder__inspector">
        <div class="ainsp__title">{{ selectedTitle }}</div>
        <template v-if="selected === 'trigger'">
          <VipSelect v-model="trigger" label="Trigger type" :options="triggerOptions" size="sm" />
          <p class="ainsp__hint">The automation runs whenever this event occurs in the workspace.</p>
        </template>
        <template v-else-if="selected === 'condition'">
          <VipInput
            v-model="condition"
            label="Condition expression"
            help="Only continue when this evaluates true. Leave empty to always run."
          />
        </template>
        <template v-else>
          <p class="ainsp__hint">
            Configure the action parameters. Connection and recipient bindings resolve from workspace settings at run
            time.
          </p>
          <VipInput
            label="Label"
            :model-value="actions.find((a) => a.id === selected)?.label ?? ''"
            size="sm"
            readonly
          />
        </template>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.abuilder {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: var(--vip-bg-canvas);
}
.abuilder__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 var(--vip-sp-5);
  background: var(--vip-surface-1);
  border-bottom: 1px solid var(--vip-border);
  flex: none;
}
.abuilder__tb-left {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.abuilder__tb-right {
  display: flex;
  gap: var(--vip-sp-3);
}
.abuilder__name {
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-sm);
  padding: 2px 6px;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.abuilder__name:hover {
  border-color: var(--vip-border);
}
.abuilder__name:focus {
  border-color: var(--vip-brand-500);
  outline: none;
}
.abuilder__body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.abuilder__flow {
  flex: 1;
  overflow-y: auto;
  padding: var(--vip-sp-9);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.aflow__wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.aflow__block {
  width: 320px;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-lg);
  padding: var(--vip-sp-5);
  border-left-width: 3px;
  cursor: pointer;
  position: relative;
}
.aflow__block.is-trigger {
  border-left-color: var(--vip-viz-2, #22c1a6);
}
.aflow__block.is-condition {
  border-left-color: var(--vip-warning);
}
.aflow__block.is-action {
  border-left-color: var(--vip-brand-500);
}
.aflow__block.is-selected {
  box-shadow: 0 0 0 2px var(--vip-brand-soft);
  border-color: var(--vip-brand-500);
}
.aflow__block-head {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
}
.aflow__block-body {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  margin-top: var(--vip-sp-3);
}
.aflow__block-actions {
  position: absolute;
  top: var(--vip-sp-4);
  right: var(--vip-sp-4);
  display: flex;
  gap: 2px;
}
.aflow__block-actions button {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
}
.aflow__block-actions button:hover:not(:disabled) {
  color: var(--vip-text-primary);
}
.aflow__block-actions button:disabled {
  opacity: 0.4;
}
.aflow__connector {
  width: 2px;
  height: 28px;
  background: var(--vip-border-strong);
}
.aflow__add {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-4) var(--vip-sp-6);
  background: none;
  border: 1px dashed var(--vip-border-strong);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
}
.aflow__add:hover {
  border-color: var(--vip-brand-500);
  color: var(--vip-brand-text);
}
.abuilder__inspector {
  width: 320px;
  flex: none;
  border-left: 1px solid var(--vip-border);
  background: var(--vip-surface-1);
  padding: var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.ainsp__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.ainsp__hint {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
</style>
