<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { NAV_GROUPS, type NavGroup, type NavItem } from '@/app/navigation'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTooltip from '@/shared/ui/VipTooltip.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const route = useRoute()

function visible(item: NavItem): boolean {
  if (item.permission && !platform.can(item.permission)) return false
  if (item.entitlement && !platform.entitled(item.entitlement)) return false
  if (item.featureFlag && !platform.flagEnabled(item.featureFlag)) return false
  return true
}

const groups = computed<NavGroup[]>(() =>
  NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter(visible) })).filter((g) => g.items.length > 0),
)

function isActive(to: string): boolean {
  if (to === '/home') return route.path === '/home' || route.path === '/'
  return route.path === to || route.path.startsWith(to + '/')
}

const collapsed = computed(() => ui.sidebarCollapsed)
</script>

<template>
  <nav class="vip-sidebar" :class="{ 'is-collapsed': collapsed }" aria-label="Primary">
    <div class="vip-sidebar__brand">
      <RouterLink to="/home" class="vip-sidebar__logo" aria-label="VIP Home">
        <span class="vip-sidebar__mark">
          <svg width="20" height="20" viewBox="0 0 32 32"><path d="M8 9l5 14 3-8 3 8 5-14" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </span>
        <span v-if="!collapsed" class="vip-sidebar__wordmark">VIP</span>
      </RouterLink>
      <button class="vip-sidebar__collapse" :aria-label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'" @click="ui.toggleSidebar()">
        <VipIcon :name="collapsed ? 'chevronRight' : 'chevronLeft'" :size="15" />
      </button>
    </div>

    <div class="vip-sidebar__scroll">
      <div v-for="group in groups" :key="group.key" class="vip-sidebar__group">
        <div v-if="!collapsed" class="vip-sidebar__group-label">{{ group.label }}</div>
        <VipTooltip
          v-for="item in group.items"
          :key="item.to"
          :text="collapsed ? item.label : ''"
          placement="right"
        >
          <RouterLink :to="item.to" class="vip-sidebar__item" :class="{ 'is-active': isActive(item.to) }">
            <VipIcon :name="item.icon" :size="17" />
            <span v-if="!collapsed" class="vip-sidebar__item-label">{{ item.label }}</span>
          </RouterLink>
        </VipTooltip>
      </div>
    </div>

    <div class="vip-sidebar__footer">
      <VipTooltip :text="collapsed ? 'Help & docs' : ''" placement="right">
        <RouterLink to="/developer" class="vip-sidebar__item">
          <VipIcon name="help" :size="17" />
          <span v-if="!collapsed" class="vip-sidebar__item-label">Help & docs</span>
        </RouterLink>
      </VipTooltip>
      <div v-if="!collapsed" class="vip-sidebar__version">VIP · v0.1.0 · mock</div>
    </div>
  </nav>
</template>

<style scoped>
.vip-sidebar {
  display: flex;
  flex-direction: column;
  width: 236px;
  background: var(--vip-surface-1);
  border-right: 1px solid var(--vip-border-subtle);
  transition: width var(--vip-motion-base) var(--vip-ease-standard);
  height: 100%;
}
.vip-sidebar.is-collapsed { width: 60px; }

.vip-sidebar__brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 var(--vip-sp-5);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.vip-sidebar__logo { display: inline-flex; align-items: center; gap: var(--vip-sp-4); text-decoration: none; }
.vip-sidebar__mark {
  width: 30px; height: 30px; border-radius: var(--vip-radius-md);
  background: linear-gradient(135deg, var(--vip-brand-500), var(--vip-brand-accent));
  color: #fff; display: inline-flex; align-items: center; justify-content: center;
}
.vip-sidebar__wordmark { font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-bold); letter-spacing: 0.06em; color: var(--vip-text-primary); }
.vip-sidebar__collapse {
  width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center;
  background: none; border: none; border-radius: var(--vip-radius-sm); color: var(--vip-text-muted);
}
.is-collapsed .vip-sidebar__collapse { display: none; }
.vip-sidebar__collapse:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }

.vip-sidebar__scroll { flex: 1; overflow-y: auto; padding: var(--vip-sp-5) var(--vip-sp-4); }
.vip-sidebar__group { margin-bottom: var(--vip-sp-6); }
.vip-sidebar__group-label {
  font-size: var(--vip-fs-2xs);
  font-weight: var(--vip-fw-semibold);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-disabled);
  padding: 0 var(--vip-sp-4);
  margin-bottom: var(--vip-sp-3);
}
.vip-sidebar__item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  text-decoration: none;
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
  transition: background var(--vip-motion-fast), color var(--vip-motion-fast);
  white-space: nowrap;
}
.is-collapsed .vip-sidebar__item { justify-content: center; padding: var(--vip-sp-3); }
.vip-sidebar__item:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.vip-sidebar__item.is-active { background: var(--vip-brand-soft); color: var(--vip-brand-text); }
.vip-sidebar__item-label { overflow: hidden; text-overflow: ellipsis; }

.vip-sidebar__footer { padding: var(--vip-sp-4); border-top: 1px solid var(--vip-border-subtle); }
.vip-sidebar__version { font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); padding: var(--vip-sp-3) var(--vip-sp-4) 0; font-family: var(--vip-font-mono); }

.vip-sidebar :deep(.vip-tt) { display: block; }
</style>
