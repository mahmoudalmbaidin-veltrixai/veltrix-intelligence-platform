<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { useThemeStore } from '@/shared/stores/theme'
import { QUICK_CREATE } from '@/app/navigation'
import { ROLES } from '@/shared/permissions/roles'
import type { RoleKey } from '@/shared/types/identity'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipAvatar from '@/shared/ui/VipAvatar.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const theme = useThemeStore()
const route = useRoute()
const router = useRouter()

const breadcrumb = computed(() => (route.meta.title as string) ?? '')

const orgItems = computed(() =>
  platform.organizations.map((o) => ({ key: o.id, label: o.name, icon: 'building' })),
)
const wsItems = computed(() =>
  platform.workspaces.map((w) => ({ key: w.id, label: w.name, icon: 'layers' })),
)
const createItems = computed(() =>
  QUICK_CREATE.filter((i) => !i.permission || platform.can(i.permission)).map((i) => ({
    key: i.to,
    label: i.label,
    icon: i.icon,
  })),
)
const roleItems = computed(() =>
  (Object.keys(ROLES) as RoleKey[]).map((r) => ({ key: r, label: ROLES[r].label, icon: 'users' })),
)

const userItems = [
  { key: '/settings/personal', label: 'Profile & preferences', icon: 'settings' },
  { key: 'appearance', label: 'Toggle appearance', icon: 'moon' },
  { key: '/settings/security', label: 'Security', icon: 'lock' },
  { key: 'divider', label: '', divider: true },
  { key: 'signout', label: 'Sign out', icon: 'logout', danger: true },
]

function onUserSelect(key: string) {
  if (key === 'appearance') theme.cycle()
  else if (key === 'signout') ui.pushToast({ kind: 'info', title: 'Sign out', message: 'Authentication is a backend dependency (mock mode).' })
  else router.push(key)
}
</script>

<template>
  <header class="vip-topbar">
    <div class="vip-topbar__left">
      <button class="vip-topbar__mobile" aria-label="Open navigation" @click="ui.mobileNavOpen = true">
        <VipIcon name="menu" :size="18" />
      </button>

      <VipMenu :items="orgItems" align="start" @select="platform.switchOrg($event)">
        <template #trigger>
          <button class="vip-switcher">
            <span class="vip-switcher__mark">{{ platform.organization.name.charAt(0) }}</span>
            <span class="vip-switcher__name">{{ platform.organization.name }}</span>
            <VipBadge v-if="platform.organization.status !== 'active'" size="sm" tone="warning">{{ platform.organization.status }}</VipBadge>
            <VipIcon name="chevronDown" :size="14" />
          </button>
        </template>
      </VipMenu>

      <span class="vip-topbar__sep">/</span>

      <VipMenu :items="wsItems" align="start" @select="platform.switchWorkspace($event)">
        <template #trigger>
          <button class="vip-switcher is-ws">
            <VipIcon name="layers" :size="15" />
            <span class="vip-switcher__name">{{ platform.workspace?.name }}</span>
            <VipIcon name="chevronDown" :size="14" />
          </button>
        </template>
      </VipMenu>

      <span v-if="breadcrumb" class="vip-topbar__sep">/</span>
      <span v-if="breadcrumb" class="vip-topbar__crumb">{{ breadcrumb }}</span>
    </div>

    <div class="vip-topbar__right">
      <button class="vip-topbar__search" @click="ui.openCommand()">
        <VipIcon name="search" :size="15" />
        <span>Search & commands</span>
        <kbd>⌘K</kbd>
      </button>

      <VipMenu :items="createItems" @select="router.push($event)">
        <template #trigger>
          <button class="vip-icon-btn is-primary" title="Create" aria-label="Create">
            <VipIcon name="plus" :size="17" />
          </button>
        </template>
      </VipMenu>

      <button class="vip-icon-btn" :title="`Theme: ${theme.mode}`" aria-label="Toggle theme" @click="theme.cycle()">
        <VipIcon :name="theme.resolved() === 'dark' ? 'sun' : 'moon'" :size="17" />
      </button>

      <button class="vip-icon-btn" title="Notifications" aria-label="Notifications" @click="ui.notificationDrawerOpen = true">
        <VipIcon name="bell" :size="17" />
        <span v-if="ui.unreadNotifications" class="vip-icon-btn__badge">{{ ui.unreadNotifications }}</span>
      </button>

      <VipMenu :items="roleItems" @select="platform.setRole($event as RoleKey)">
        <template #trigger>
          <button class="vip-role" title="Simulate role (dev)">
            <VipIcon name="users" :size="14" />
            <span>{{ ROLES[platform.role].label }}</span>
            <VipIcon name="chevronDown" :size="13" />
          </button>
        </template>
      </VipMenu>

      <VipMenu :items="userItems" @select="onUserSelect">
        <template #trigger>
          <button class="vip-topbar__user" aria-label="User menu">
            <VipAvatar :name="platform.user.name" :color="platform.user.avatarColor" :size="28" />
          </button>
        </template>
      </VipMenu>
    </div>
  </header>
</template>

<style scoped>
.vip-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 var(--vip-sp-6);
  background: var(--vip-surface-1);
  border-bottom: 1px solid var(--vip-border-subtle);
  gap: var(--vip-sp-5);
}
.vip-topbar__left, .vip-topbar__right { display: flex; align-items: center; gap: var(--vip-sp-4); min-width: 0; }
.vip-topbar__mobile { display: none; background: none; border: none; color: var(--vip-text-secondary); }

.vip-switcher {
  display: inline-flex; align-items: center; gap: var(--vip-sp-3);
  height: 32px; padding: 0 var(--vip-sp-4);
  background: none; border: 1px solid transparent; border-radius: var(--vip-radius-md);
  color: var(--vip-text-primary); font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium);
}
.vip-switcher:hover { background: var(--vip-surface-hover); border-color: var(--vip-border); }
.vip-switcher__mark {
  width: 20px; height: 20px; border-radius: var(--vip-radius-sm);
  background: var(--vip-brand-500); color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: var(--vip-fs-xs); font-weight: var(--vip-fw-bold);
}
.vip-switcher__name { max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vip-topbar__sep { color: var(--vip-text-disabled); }
.vip-topbar__crumb { color: var(--vip-text-secondary); font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); }

.vip-topbar__search {
  display: inline-flex; align-items: center; gap: var(--vip-sp-4);
  height: 32px; padding: 0 var(--vip-sp-4) 0 var(--vip-sp-5);
  min-width: 240px;
  background: var(--vip-surface-2); border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md); color: var(--vip-text-muted); font-size: var(--vip-fs-sm);
}
.vip-topbar__search:hover { border-color: var(--vip-border-strong); }
.vip-topbar__search span { flex: 1; text-align: left; }
.vip-topbar__search kbd {
  font-family: var(--vip-font-mono); font-size: var(--vip-fs-2xs);
  background: var(--vip-surface-3); padding: 2px 5px; border-radius: var(--vip-radius-xs);
}

.vip-icon-btn {
  position: relative;
  width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center;
  background: none; border: 1px solid transparent; border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
}
.vip-icon-btn:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.vip-icon-btn.is-primary { background: var(--vip-brand-500); color: #fff; }
.vip-icon-btn.is-primary:hover { background: var(--vip-brand-600); }
.vip-icon-btn__badge {
  position: absolute; top: -3px; right: -3px;
  min-width: 16px; height: 16px; padding: 0 4px;
  background: var(--vip-danger); color: #fff; border-radius: var(--vip-radius-full);
  font-size: var(--vip-fs-2xs); font-weight: var(--vip-fw-bold);
  display: inline-flex; align-items: center; justify-content: center;
}

.vip-role {
  display: inline-flex; align-items: center; gap: var(--vip-sp-3);
  height: 30px; padding: 0 var(--vip-sp-4);
  background: var(--vip-surface-2); border: 1px solid var(--vip-border); border-radius: var(--vip-radius-full);
  color: var(--vip-text-secondary); font-size: var(--vip-fs-xs); font-weight: var(--vip-fw-medium);
}
.vip-role:hover { border-color: var(--vip-border-strong); color: var(--vip-text-primary); }
.vip-topbar__user { background: none; border: none; padding: 0; border-radius: 50%; }

@media (max-width: 1024px) {
  .vip-topbar__search span { display: none; }
  .vip-topbar__search { min-width: 0; }
  .vip-switcher.is-ws { display: none; }
}
@media (max-width: 768px) {
  .vip-topbar__mobile { display: inline-flex; }
  .vip-role { display: none; }
  .vip-topbar__crumb, .vip-topbar__sep { display: none; }
}
</style>
