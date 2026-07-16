<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import VipIcon from './VipIcon.vue'

export interface MenuItem {
  key: string
  label: string
  icon?: string
  danger?: boolean
  disabled?: boolean
  divider?: boolean
  shortcut?: string
}

withDefaults(
  defineProps<{ items: MenuItem[]; align?: 'start' | 'end'; label?: string }>(),
  { align: 'end' },
)
const emit = defineEmits<{ select: [string] }>()

const open = ref(false)
const root = ref<HTMLElement>()

function toggle() {
  open.value = !open.value
}
function close() {
  open.value = false
}
function choose(item: MenuItem) {
  if (item.disabled || item.divider) return
  emit('select', item.key)
  close()
}
function onDocClick(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) close()
}
document.addEventListener('click', onDocClick)
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <div ref="root" class="vip-menu">
    <div class="vip-menu__trigger" @click="toggle">
      <slot name="trigger" :open="open">
        <button type="button" class="vip-menu__default-trigger" :aria-expanded="open">
          {{ label }}<VipIcon name="chevronDown" :size="14" />
        </button>
      </slot>
    </div>
    <Transition name="vip-menu-pop">
      <div v-if="open" class="vip-menu__panel" :class="`is-${align}`" role="menu" @keydown.esc="close">
        <template v-for="item in items" :key="item.key">
          <div v-if="item.divider" class="vip-menu__divider" role="separator" />
          <button
            v-else
            type="button"
            role="menuitem"
            class="vip-menu__item"
            :class="{ 'is-danger': item.danger, 'is-disabled': item.disabled }"
            :disabled="item.disabled"
            @click="choose(item)"
          >
            <VipIcon v-if="item.icon" :name="item.icon" :size="15" />
            <span class="vip-menu__item-label">{{ item.label }}</span>
            <kbd v-if="item.shortcut" class="vip-menu__kbd">{{ item.shortcut }}</kbd>
          </button>
        </template>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.vip-menu { position: relative; display: inline-flex; }
.vip-menu__trigger { display: inline-flex; }
.vip-menu__default-trigger {
  display: inline-flex; align-items: center; gap: var(--vip-sp-3);
  height: 32px; padding: 0 var(--vip-sp-5);
  background: var(--vip-surface-2); border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md); color: var(--vip-text-primary); font-size: var(--vip-fs-md);
}
.vip-menu__panel {
  position: absolute;
  top: calc(100% + 6px);
  min-width: 190px;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  box-shadow: var(--vip-shadow-lg);
  padding: var(--vip-sp-2);
  z-index: var(--vip-z-dropdown);
}
.is-end { right: 0; }
.is-start { left: 0; }
.vip-menu__item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  width: 100%;
  padding: var(--vip-sp-3) var(--vip-sp-4);
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-md);
  text-align: left;
}
.vip-menu__item:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.vip-menu__item.is-danger { color: var(--vip-danger-text); }
.vip-menu__item.is-danger:hover { background: var(--vip-danger-soft); }
.vip-menu__item.is-disabled { opacity: 0.45; pointer-events: none; }
.vip-menu__item-label { flex: 1; }
.vip-menu__kbd {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
  background: var(--vip-surface-3);
  padding: 1px 5px;
  border-radius: var(--vip-radius-xs);
}
.vip-menu__divider { height: 1px; background: var(--vip-border-subtle); margin: var(--vip-sp-2) 0; }

.vip-menu-pop-enter-active { transition: opacity var(--vip-motion-fast), transform var(--vip-motion-fast); }
.vip-menu-pop-enter-from { opacity: 0; transform: translateY(-4px); }
</style>
