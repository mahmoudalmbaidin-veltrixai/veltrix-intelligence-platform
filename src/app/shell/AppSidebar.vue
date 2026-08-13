<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { NAV_GROUPS, canExposeNavigationItem, type NavGroup, type NavItem } from '@/app/navigation'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { announce } from '@/shared/composables/useAnnouncer'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTooltip from '@/shared/ui/VipTooltip.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const route = useRoute()

const railEl = ref<HTMLElement>()
/** Temporary expansion driven by hover/focus while the rail is collapsed. */
const hovered = ref(false)
let hoverTimer: ReturnType<typeof setTimeout> | undefined

function visible(item: NavItem): boolean {
  return canExposeNavigationItem(item, platform)
}

const groups = computed<NavGroup[]>(() =>
  NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter(visible) })).filter((g) => g.items.length > 0),
)

function isActive(to: string): boolean {
  if (to === '/home') return route.path === '/home' || route.path === '/'
  return route.path === to || route.path.startsWith(to + '/')
}

// Pinned open = not collapsed. Collapsed rail shows icons only and reveals
// labels on hover/focus as a floating overlay.
const collapsed = computed(() => ui.sidebarCollapsed)
const expanded = computed(() => !collapsed.value || hovered.value)
/** True only while temporarily floating over content (collapsed + hover/focus). */
const floating = computed(() => collapsed.value && hovered.value)

function clearHoverTimer() {
  if (hoverTimer) {
    clearTimeout(hoverTimer)
    hoverTimer = undefined
  }
}

function onRailEnter() {
  if (!collapsed.value) return
  // Dwell long enough for collapsed icon tooltips to paint before the rail
  // floats open (WebKit was losing the tooltip during the remount/layout).
  clearHoverTimer()
  hoverTimer = setTimeout(() => (hovered.value = true), 420)
}
function onRailLeave() {
  clearHoverTimer()
  // Keep expanded if focus is still inside (keyboard navigation).
  if (railEl.value?.contains(document.activeElement)) return
  hovered.value = false
}
function onRailFocusin() {
  if (collapsed.value) hovered.value = true
}
function onRailFocusout(e: FocusEvent) {
  const next = e.relatedTarget as Node | null
  if (next && railEl.value?.contains(next)) return
  hovered.value = false
}

function togglePin() {
  ui.toggleSidebar()
  hovered.value = false
  announce(ui.sidebarCollapsed ? 'Navigation collapsed to icons' : 'Navigation pinned open')
}

function onWindowKey(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null
  const isEditing =
    target?.matches('input, textarea, select') ||
    target?.isContentEditable ||
    target?.closest('[contenteditable="true"]')
  if (isEditing) return

  // Ctrl/Cmd+B toggles the sidebar (pin / collapse).
  if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'b') {
    e.preventDefault()
    togglePin()
    return
  }
  // Escape closes a temporary hover/focus expansion.
  if (e.key === 'Escape' && floating.value) {
    hovered.value = false
    if (railEl.value?.contains(document.activeElement)) {
      ;(document.activeElement as HTMLElement | null)?.blur()
    }
  }
}

// Pinning open cancels any pending overlay state.
watch(collapsed, (c) => {
  if (!c) hovered.value = false
})

onMounted(() => window.addEventListener('keydown', onWindowKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onWindowKey)
  clearHoverTimer()
})
</script>

<template>
  <div
    ref="railEl"
    class="vip-rail"
    :class="{ 'is-collapsed': collapsed, 'is-expanded': expanded, 'is-floating': floating }"
    @mouseenter="onRailEnter"
    @mouseleave="onRailLeave"
    @focusin="onRailFocusin"
    @focusout="onRailFocusout"
  >
    <nav class="vip-sidebar" aria-label="Primary navigation" :aria-expanded="expanded">
      <div class="vip-sidebar__brand">
        <RouterLink to="/home" class="vip-sidebar__logo" aria-label="VIP home">
          <VipLogo :variant="expanded ? 'full' : 'icon'" size="sm" decorative />
        </RouterLink>
        <button
          class="vip-sidebar__pin"
          :class="{ 'is-active': !collapsed }"
          :aria-pressed="!collapsed"
          :aria-label="collapsed ? 'Pin navigation open' : 'Unpin and collapse navigation to icons'"
          :title="`${collapsed ? 'Pin open' : 'Collapse to icons'} · Ctrl+B`"
          @click="togglePin"
        >
          <VipIcon :name="collapsed ? 'pin' : 'pinOff'" :size="15" />
        </button>
      </div>

      <div class="vip-sidebar__scroll">
        <div v-for="group in groups" :key="group.key" class="vip-sidebar__group">
          <div class="vip-sidebar__group-label" :hidden="!expanded">{{ group.label }}</div>
          <VipTooltip
            v-for="item in group.items"
            :key="item.to"
            :text="collapsed ? item.label : ''"
            :description="collapsed ? item.description : ''"
            :shortcut="collapsed ? item.shortcut : ''"
            placement="right"
          >
            <RouterLink
              :to="item.to"
              class="vip-sidebar__item"
              :class="{ 'is-active': isActive(item.to) }"
              :aria-label="collapsed && !floating ? item.label : undefined"
              :aria-current="isActive(item.to) ? 'page' : undefined"
            >
              <VipIcon :name="item.icon" :size="17" class="vip-sidebar__item-icon" />
              <span class="vip-sidebar__item-label" :hidden="!expanded">{{ item.label }}</span>
            </RouterLink>
          </VipTooltip>
        </div>
      </div>

      <div class="vip-sidebar__footer">
        <VipTooltip
          :text="collapsed ? 'Help & docs' : ''"
          :description="collapsed ? 'Guides, API reference and support.' : ''"
          placement="right"
        >
          <RouterLink
            to="/help"
            class="vip-sidebar__item"
            :aria-label="collapsed && !floating ? 'Help & docs' : undefined"
          >
            <VipIcon name="help" :size="17" class="vip-sidebar__item-icon" />
            <span class="vip-sidebar__item-label" :hidden="!expanded">Help &amp; docs</span>
          </RouterLink>
        </VipTooltip>
        <div class="vip-sidebar__version" :hidden="!expanded">VIP · v0.1.0 · hybrid local</div>
      </div>
    </nav>
  </div>
</template>

<style scoped>
/* Rail occupies layout space; the sidebar within can float wider on hover. */
.vip-rail {
  position: relative;
  flex: none;
  height: 100%;
  width: 236px;
  transition: width var(--vip-motion-base) var(--vip-ease-emphasized);
}
.vip-rail.is-collapsed {
  width: 60px;
}
.vip-rail.is-floating {
  z-index: var(--vip-z-popover);
}

.vip-sidebar {
  position: absolute;
  inset: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: var(--vip-surface-1);
  border-right: 1px solid var(--vip-border-subtle);
  overflow: hidden;
  transition:
    width var(--vip-motion-base) var(--vip-ease-emphasized),
    box-shadow var(--vip-motion-base) var(--vip-ease-standard);
}
/* When collapsed + hovered, expand as a floating overlay above the content. */
.vip-rail.is-floating .vip-sidebar {
  width: 236px;
  box-shadow: var(--vip-shadow-lg);
  border-right-color: var(--vip-border);
}

.vip-sidebar__brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 var(--vip-sp-5);
  border-bottom: 1px solid var(--vip-border-subtle);
  flex: none;
}
.is-collapsed:not(.is-floating) .vip-sidebar__brand {
  justify-content: space-between;
  padding: 0 var(--vip-sp-3);
}
.is-collapsed:not(.is-floating) .vip-sidebar__pin {
  width: 22px;
  height: 26px;
}
.vip-sidebar__logo {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  color: var(--vip-text-primary);
  border-radius: var(--vip-radius-sm);
}
.vip-sidebar__pin {
  width: 26px;
  height: 26px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
  transition:
    background var(--vip-motion-fast),
    color var(--vip-motion-fast),
    transform var(--vip-motion-fast);
}
.vip-sidebar__pin:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.vip-sidebar__pin.is-active {
  color: var(--vip-brand-text);
}
.vip-sidebar__pin.is-active:hover {
  color: var(--vip-brand-text);
}

.vip-sidebar__scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--vip-sp-5) var(--vip-sp-4);
}
.vip-sidebar__group {
  margin-bottom: var(--vip-sp-6);
}
.vip-sidebar__group-label {
  font-size: var(--vip-fs-2xs);
  font-weight: var(--vip-fw-semibold);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-disabled);
  padding: 0 var(--vip-sp-4);
  margin-bottom: var(--vip-sp-3);
  white-space: nowrap;
  animation: vip-nav-reveal var(--vip-motion-base) var(--vip-ease-standard);
}
.vip-sidebar__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  text-decoration: none;
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  transition:
    background var(--vip-motion-fast),
    color var(--vip-motion-fast);
  white-space: nowrap;
}
.is-collapsed:not(.is-floating) .vip-sidebar__item {
  justify-content: center;
  padding: var(--vip-sp-3);
}
.vip-sidebar__item-icon {
  flex: none;
}
.vip-sidebar__item:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.vip-sidebar__item.is-active {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  font-weight: var(--vip-fw-semibold);
}
/* Left accent bar makes the current page unmistakable, collapsed or expanded. */
.vip-sidebar__item.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 18px;
  width: 3px;
  border-radius: 0 var(--vip-radius-full) var(--vip-radius-full) 0;
  background: var(--vip-brand-500);
}
.is-collapsed:not(.is-floating) .vip-sidebar__item.is-active::before {
  left: -2px;
}
.vip-sidebar__item-label {
  overflow: hidden;
  text-overflow: ellipsis;
  animation: vip-nav-reveal var(--vip-motion-base) var(--vip-ease-standard);
}

.vip-sidebar__footer {
  padding: var(--vip-sp-4);
  border-top: 1px solid var(--vip-border-subtle);
  flex: none;
}
.is-collapsed:not(.is-floating) .vip-sidebar__footer {
  padding: var(--vip-sp-4) var(--vip-sp-3);
}
.vip-sidebar__version {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
  padding: var(--vip-sp-3) var(--vip-sp-4) 0;
  font-family: var(--vip-font-mono);
  white-space: nowrap;
}

.vip-sidebar :deep(.vip-tt) {
  display: block;
}

@keyframes vip-nav-reveal {
  from {
    opacity: 0;
    transform: translateX(-6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
