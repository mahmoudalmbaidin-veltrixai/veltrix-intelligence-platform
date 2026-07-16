<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { NAV_GROUPS, type NavItem } from '@/app/navigation'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import VipDrawer from '@/shared/ui/VipDrawer.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const route = useRoute()

function visible(item: NavItem): boolean {
  if (item.permission && !platform.can(item.permission)) return false
  if (item.entitlement && !platform.entitled(item.entitlement)) return false
  if (item.featureFlag && !platform.flagEnabled(item.featureFlag)) return false
  return true
}
const groups = computed(() =>
  NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter(visible) })).filter((g) => g.items.length),
)
</script>

<template>
  <VipDrawer :open="ui.mobileNavOpen" title="Navigation" side="left" :width="280" @close="ui.mobileNavOpen = false">
    <div v-for="group in groups" :key="group.key" class="mnav__group">
      <div class="mnav__label">{{ group.label }}</div>
      <RouterLink
        v-for="item in group.items"
        :key="item.to"
        :to="item.to"
        class="mnav__item"
        :class="{ 'is-active': route.path.startsWith(item.to) }"
        @click="ui.mobileNavOpen = false"
      >
        <VipIcon :name="item.icon" :size="17" />
        {{ item.label }}
      </RouterLink>
    </div>
  </VipDrawer>
</template>

<style scoped>
.mnav__group { margin-bottom: var(--vip-sp-6); }
.mnav__label { font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-disabled); margin-bottom: var(--vip-sp-3); }
.mnav__item {
  display: flex; align-items: center; gap: var(--vip-sp-4);
  padding: var(--vip-sp-4); border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary); text-decoration: none; font-weight: var(--vip-fw-medium);
}
.mnav__item.is-active { background: var(--vip-brand-soft); color: var(--vip-brand-text); }
</style>
