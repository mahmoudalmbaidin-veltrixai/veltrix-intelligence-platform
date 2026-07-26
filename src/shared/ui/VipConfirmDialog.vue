<script setup lang="ts">
/**
 * Reusable enterprise confirmation dialog for lifecycle / destructive actions
 * (archive, disable, delete, restore). Built on VipDialog so it inherits focus
 * trap, focus restoration and scrim behaviour.
 *
 * Safety features:
 *  - Levels drive tone: warning (archive/disable), danger (delete), neutral (restore).
 *  - Optional typed confirmation (e.g. type the resource name to delete).
 *  - Loading state disables inputs + prevents double-submit and disables ESC/close.
 *  - Backend error is shown in-dialog (dialog stays open) and announced.
 *  - The parent owns the async call; this component only reflects pending/error.
 */
import { computed, ref, watch, nextTick } from 'vue'
import VipDialog from './VipDialog.vue'
import VipButton from './VipButton.vue'
import VipAlert from './VipAlert.vue'
import VipIcon from './VipIcon.vue'
import { announce } from '@/shared/composables/useAnnouncer'

const props = withDefaults(
  defineProps<{
    open: boolean
    level?: 'danger' | 'warning' | 'neutral'
    title: string
    /** Resource name, rendered emphasized and used as the typed-confirmation target. */
    resourceName?: string
    /** Primary explanation of what will happen. */
    message?: string
    /** Bullet list of concrete consequences. */
    impact?: string[]
    /** Extra note, e.g. reversibility. Keep honest — do not imply restore if unsupported. */
    note?: string
    confirmLabel?: string
    cancelLabel?: string
    /** Require the user to type `resourceName` (or `typedTarget`) before confirming. */
    requireTyping?: boolean
    typedTarget?: string
    /** In-flight: disables actions, shows spinner, blocks ESC/close. */
    pending?: boolean
    /** Safe, backend-provided error message to display (never raw internals). */
    error?: string | null
  }>(),
  { level: 'warning', cancelLabel: 'Cancel' },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()

const typed = ref('')
const target = computed(() => props.typedTarget ?? props.resourceName ?? '')
const typedOk = computed(() => !props.requireTyping || typed.value.trim() === target.value.trim())
const canConfirm = computed(() => !props.pending && typedOk.value)

const confirmVariant = computed(() => (props.level === 'danger' ? 'danger' : 'primary'))
const defaultConfirm = computed(() =>
  props.level === 'danger' ? 'Delete' : props.level === 'neutral' ? 'Restore' : 'Archive',
)
const iconName = computed(() => (props.level === 'danger' ? 'trash' : props.level === 'neutral' ? 'undo' : 'archive'))

function onConfirm() {
  if (!canConfirm.value) return
  emit('confirm')
}
function onCancel() {
  if (props.pending) return
  emit('cancel')
}

// Reset the typed field each time the dialog opens; announce lifecycle changes.
watch(
  () => props.open,
  async (open) => {
    if (open) {
      typed.value = ''
      await nextTick()
      if (props.requireTyping) {
        document.getElementById('vip-confirm-typed')?.focus()
      }
    }
  },
)
watch(
  () => props.pending,
  (p) => {
    if (p) announce('Working, please wait', 'polite')
  },
)
watch(
  () => props.error,
  (e) => {
    if (e) announce(`Action failed. ${e}`, 'assertive')
  },
)
</script>

<template>
  <VipDialog :open="open" :title="title" :closable="!pending" size="sm" @close="onCancel">
    <div class="vc" :class="`vc--${level}`">
      <div class="vc__head">
        <span class="vc__icon"><VipIcon :name="iconName" :size="18" /></span>
        <div class="vc__lead">
          <p v-if="message" class="vc__msg">{{ message }}</p>
          <p v-if="resourceName" class="vc__resource">“{{ resourceName }}”</p>
        </div>
      </div>

      <ul v-if="impact && impact.length" class="vc__impact">
        <li v-for="(line, i) in impact" :key="i">{{ line }}</li>
      </ul>

      <p v-if="note" class="vc__note">{{ note }}</p>

      <div v-if="requireTyping" class="vc__typed">
        <label for="vip-confirm-typed" class="vc__typed-label">
          Type <strong>{{ target }}</strong> to confirm
        </label>
        <input
          id="vip-confirm-typed"
          v-model="typed"
          class="vc__typed-input"
          type="text"
          autocomplete="off"
          spellcheck="false"
          :disabled="pending"
          :aria-invalid="!typedOk && typed.length > 0"
          :placeholder="target"
        />
      </div>

      <VipAlert v-if="error" tone="danger" title="Action failed" class="vc__error">{{ error }}</VipAlert>
    </div>

    <template #footer>
      <VipButton variant="tertiary" :disabled="pending" @click="onCancel">{{ cancelLabel }}</VipButton>
      <VipButton :variant="confirmVariant" :loading="pending" :disabled="!canConfirm" data-autofocus @click="onConfirm">
        {{ confirmLabel ?? defaultConfirm }}
      </VipButton>
    </template>
  </VipDialog>
</template>

<style scoped>
.vc {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.vc__head {
  display: flex;
  gap: var(--vip-sp-4);
  align-items: flex-start;
}
.vc__icon {
  flex: none;
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
}
.vc--danger .vc__icon {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.vc--warning .vc__icon {
  background: var(--vip-warning-soft);
  color: var(--vip-warning-text);
}
.vc--neutral .vc__icon {
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.vc__msg {
  font-size: var(--vip-fs-md);
  color: var(--vip-text-primary);
  line-height: 1.5;
}
.vc__resource {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin-top: var(--vip-sp-2);
  font-weight: var(--vip-fw-medium);
}
.vc__impact {
  margin: 0;
  padding-left: var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.vc__impact li::marker {
  color: var(--vip-text-disabled);
}
.vc__note {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  background: var(--vip-surface-2);
  border-radius: var(--vip-radius-md);
  border: 1px solid var(--vip-border-subtle);
}
.vc__typed {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.vc__typed-label {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.vc__typed-input {
  height: 34px;
  padding: 0 var(--vip-sp-5);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  font-family: var(--vip-font-mono);
}
.vc__typed-input:focus {
  outline: none;
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.vc__typed-input[aria-invalid='true'] {
  border-color: var(--vip-danger);
}
.vc__error {
  margin-top: var(--vip-sp-2);
}
</style>
