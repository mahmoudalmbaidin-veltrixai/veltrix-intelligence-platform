<script setup lang="ts">
import { watch, onBeforeUnmount, ref, nextTick } from 'vue'
import VipIcon from './VipIcon.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    side?: 'right' | 'left'
    width?: number
    /** Allow closing by swiping toward the anchored edge (touch). */
    swipeToClose?: boolean
  }>(),
  {
    side: 'right',
    width: 440,
    swipeToClose: true,
  },
)
const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement>()
let lastFocused: HTMLElement | null = null

function restoreFocus() {
  if (lastFocused?.isConnected) lastFocused.focus({ preventScroll: true })
  lastFocused = null
}

// Swipe-to-dismiss: a horizontal drag toward the anchored edge closes the drawer.
let touchStartX = 0
let touchStartY = 0
let tracking = false
function onTouchStart(e: TouchEvent) {
  if (!props.swipeToClose || e.touches.length !== 1) return
  tracking = true
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}
function onTouchEnd(e: TouchEvent) {
  if (!tracking) return
  tracking = false
  const t = e.changedTouches[0]
  const dx = t.clientX - touchStartX
  const dy = t.clientY - touchStartY
  if (Math.abs(dx) < 56 || Math.abs(dx) <= Math.abs(dy)) return
  // Left drawer closes on swipe-left; right drawer closes on swipe-right.
  if ((props.side === 'left' && dx < 0) || (props.side === 'right' && dx > 0)) emit('close')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close')
    return
  }
  if (e.key !== 'Tab' || !panel.value) return
  const focusables = panel.value.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
  )
  if (!focusables.length) return
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  async (v) => {
    document.body.style.overflow = v ? 'hidden' : ''
    if (v) {
      lastFocused = document.activeElement as HTMLElement
      await nextTick()
      panel.value?.querySelector<HTMLElement>('[data-autofocus], button, input, textarea, select, a[href]')?.focus()
    }
  },
)
onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="vip-drawer" @after-leave="restoreFocus">
      <div v-if="open" class="vip-drawer__scrim" @click.self="emit('close')" @keydown="onKeydown">
        <aside
          ref="panel"
          class="vip-drawer"
          :class="`is-${side}`"
          :style="{ width: `${width}px` }"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          @touchstart.passive="onTouchStart"
          @touchend="onTouchEnd"
        >
          <header class="vip-drawer__header">
            <h2 class="vip-drawer__title">{{ title }}</h2>
            <button type="button" class="vip-drawer__close" aria-label="Close" @click="emit('close')">
              <VipIcon name="close" :size="16" />
            </button>
          </header>
          <div class="vip-drawer__body"><slot /></div>
          <footer v-if="$slots.footer" class="vip-drawer__footer"><slot name="footer" /></footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.vip-drawer__scrim {
  position: fixed;
  inset: 0;
  background: var(--vip-scrim);
  z-index: var(--vip-z-drawer);
  display: flex;
}
.is-right {
  margin-left: auto;
}
.vip-drawer {
  background: var(--vip-surface-1);
  border-left: 1px solid var(--vip-border);
  height: 100%;
  display: flex;
  flex-direction: column;
  max-width: 96vw;
  box-shadow: var(--vip-shadow-lg);
}
.is-left {
  border-left: none;
  border-right: 1px solid var(--vip-border);
}
.vip-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-6) var(--vip-sp-7);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.vip-drawer__title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.vip-drawer__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
}
.vip-drawer__close:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.vip-drawer__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--vip-sp-7);
}
.vip-drawer__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-5) var(--vip-sp-7);
  border-top: 1px solid var(--vip-border-subtle);
}

.vip-drawer-enter-active,
.vip-drawer-leave-active {
  transition: opacity var(--vip-motion-base);
}
.vip-drawer-enter-active .vip-drawer,
.vip-drawer-leave-active .vip-drawer {
  transition: transform var(--vip-motion-base) var(--vip-ease-emphasized);
}
.vip-drawer-enter-from,
.vip-drawer-leave-to {
  opacity: 0;
}
.vip-drawer-enter-from .is-right,
.vip-drawer-leave-to .is-right {
  transform: translateX(100%);
}
.vip-drawer-enter-from .is-left,
.vip-drawer-leave-to .is-left {
  transform: translateX(-100%);
}
</style>
