<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { NAV_GROUPS, canExposeNavigationItem, type NavItem } from '@/app/navigation'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const route = useRoute()

function visible(item: NavItem): boolean {
  return canExposeNavigationItem(item, platform)
}
const groups = computed(() =>
  NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter(visible) })).filter((g) => g.items.length),
)

function isActive(to: string): boolean {
  if (to === '/home') return route.path === '/home' || route.path === '/'
  return route.path === to || route.path.startsWith(to + '/')
}
</script>

<template>
  <VipDrawer :open="ui.mobileNavOpen" title="Navigation" side="left" :width="280" @close="ui.mobileNavOpen = false">
    <RouterLink to="/home" class="mnav__brand" aria-label="Veltrix One home" @click="ui.mobileNavOpen = false">
      <VipLogo variant="full" size="md" decorative />
    </RouterLink>
    <div v-for="group in groups" :key="group.key" class="mnav__group">
      <div class="mnav__label">{{ group.label }}</div>
      <RouterLink
        v-for="item in group.items"
        :key="item.to"
        :to="item.to"
        class="mnav__item"
        :class="{ 'is-active': isActive(item.to) }"
        :aria-current="isActive(item.to) ? 'page' : undefined"
        @click="ui.mobileNavOpen = false"
      >
        <VipIcon :name="item.icon" :size="17" />
        {{ item.label }}
      </RouterLink>
    </div>
  </VipDrawer>
</template>

<style scoped>
.mnav__brand {
  display: inline-flex;
  align-items: center;
  padding: var(--vip-sp-2) 0 var(--vip-sp-5);
  margin-bottom: var(--vip-sp-4);
  color: var(--vip-text-primary);
  text-decoration: none;
  border-radius: var(--vip-radius-sm);
}
.mnav__group {
  margin-bottom: var(--vip-sp-6);
}
.mnav__label {
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-disabled);
  margin-bottom: var(--vip-sp-3);
}
.mnav__item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  text-decoration: none;
  font-weight: var(--vip-fw-medium);
}
.mnav__item.is-active {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
</style>
