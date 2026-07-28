<script setup lang="ts">
import { ref, nextTick, onBeforeUnmount } from 'vue'
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

const props = withDefaults(defineProps<{ items: MenuItem[]; align?: 'start' | 'end'; label?: string }>(), {
  align: 'end',
})
const emit = defineEmits<{ select: [string] }>()

const open = ref(false)
const root = ref<HTMLElement>()
const panel = ref<HTMLElement>()
// The panel is teleported to <body> and positioned with fixed coordinates so it
// can never be clipped by an ancestor's `overflow: hidden` (cards, tables) or
// trapped in a low stacking context. Coordinates are derived from the trigger.
const pos = ref<{ top: number; left: number; minWidth: number }>({ top: 0, left: 0, minWidth: 190 })

function triggerEl() {
  return root.value?.querySelector<HTMLElement>('.vip-menu__trigger')
}

function updatePosition() {
  const trigger = triggerEl()
  const p = panel.value
  if (!trigger || !p) return
  const t = trigger.getBoundingClientRect()
  const pw = p.offsetWidth
  const ph = p.offsetHeight
  const gap = 6
  const margin = 8
  const vw = window.innerWidth
  const vh = window.innerHeight
  let left = props.align === 'end' ? t.right - pw : t.left
  left = Math.min(Math.max(margin, left), Math.max(margin, vw - pw - margin))
  let top = t.bottom + gap
  // Flip above the trigger when there is not enough room below.
  if (top + ph > vh - margin && t.top - gap - ph > margin) {
    top = t.top - gap - ph
  }
  top = Math.min(Math.max(margin, top), Math.max(margin, vh - ph - margin))
  pos.value = { top, left, minWidth: Math.max(t.width, 190) }
}

async function toggle() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    updatePosition()
    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
    focusItem(0)
  } else {
    stopTracking()
  }
}
function stopTracking() {
  window.removeEventListener('scroll', updatePosition, true)
  window.removeEventListener('resize', updatePosition)
}
function focusTrigger() {
  triggerEl()?.querySelector<HTMLElement>('button, [href], [tabindex]:not([tabindex="-1"])')?.focus()
}
function close(restoreFocus = false) {
  if (!open.value) return
  open.value = false
  stopTracking()
  if (restoreFocus) nextTick(focusTrigger)
}

function menuItems(): HTMLElement[] {
  return panel.value ? [...panel.value.querySelectorAll<HTMLElement>('.vip-menu__item:not(:disabled)')] : []
}
function focusItem(index: number) {
  const items = menuItems()
  if (!items.length) return
  const i = (index + items.length) % items.length
  items[i]?.focus()
}
function onMenuKeydown(e: KeyboardEvent) {
  const items = menuItems()
  const current = items.indexOf(document.activeElement as HTMLElement)
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    focusItem(current + 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    focusItem(current - 1)
  } else if (e.key === 'Home') {
    e.preventDefault()
    focusItem(0)
  } else if (e.key === 'End') {
    e.preventDefault()
    focusItem(items.length - 1)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    close(true)
  } else if (e.key === 'Tab') {
    close()
  }
}
function choose(item: MenuItem) {
  if (item.disabled || item.divider) return
  emit('select', item.key)
  close()
}
function onDocClick(e: MouseEvent) {
  const target = e.target as Node
  if (root.value?.contains(target) || panel.value?.contains(target)) return
  close()
}
document.addEventListener('click', onDocClick)
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  stopTracking()
})
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
    <Teleport to="body">
      <Transition name="vip-menu-pop">
        <div
          v-if="open"
          ref="panel"
          class="vip-menu__panel"
          role="menu"
          :style="{ top: `${pos.top}px`, left: `${pos.left}px`, minWidth: `${pos.minWidth}px` }"
          @keydown="onMenuKeydown"
        >
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
    </Teleport>
  </div>
</template>

<style scoped>
.vip-menu {
  position: relative;
  display: inline-flex;
}
.vip-menu__trigger {
  display: inline-flex;
}
.vip-menu__default-trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  height: 32px;
  padding: 0 var(--vip-sp-5);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
}
</style>

<style>
/* Unscoped: the panel is teleported to <body>, outside this component's DOM. */
.vip-menu__panel {
  position: fixed;
  min-width: 190px;
  max-width: min(320px, calc(100vw - 16px));
  max-height: calc(100vh - 16px);
  overflow-y: auto;
  overscroll-behavior: contain;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  box-shadow: var(--vip-shadow-lg);
  padding: var(--vip-sp-2);
  z-index: var(--vip-z-popover);
}
.vip-menu__panel .vip-menu__item {
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
  cursor: pointer;
}
.vip-menu__panel .vip-menu__item:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.vip-menu__panel .vip-menu__item.is-danger {
  color: var(--vip-danger-text);
}
.vip-menu__panel .vip-menu__item.is-danger:hover {
  background: var(--vip-danger-soft);
}
.vip-menu__panel .vip-menu__item.is-disabled {
  opacity: 0.45;
  pointer-events: none;
}
.vip-menu__panel .vip-menu__item-label {
  flex: 1;
}
.vip-menu__panel .vip-menu__kbd {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
  background: var(--vip-surface-3);
  padding: 1px 5px;
  border-radius: var(--vip-radius-xs);
}
.vip-menu__panel .vip-menu__divider {
  height: 1px;
  background: var(--vip-border-subtle);
  margin: var(--vip-sp-2) 0;
}
.vip-menu-pop-enter-active {
  transition:
    opacity var(--vip-motion-fast),
    transform var(--vip-motion-fast);
}
.vip-menu-pop-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
