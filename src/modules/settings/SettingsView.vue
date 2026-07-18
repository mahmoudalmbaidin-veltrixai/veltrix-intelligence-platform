<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { useThemeStore, type ThemeMode } from '@/shared/stores/theme'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import { isoAgo } from '@/shared/lib/mock'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import type { Permission } from '@/shared/types/identity'

const route = useRoute()
const router = useRouter()
const platform = usePlatformStore()
const theme = useThemeStore()
const ui = useUiStore()

interface NavItem {
  key: string
  label: string
}
interface NavGroup {
  label: string
  permission?: Permission
  items: NavItem[]
}
const groups: NavGroup[] = [
  {
    label: 'Personal',
    items: [
      { key: 'personal', label: 'Profile' },
      { key: 'appearance', label: 'Appearance' },
      { key: 'language', label: 'Language & region' },
      { key: 'notifications', label: 'Notifications' },
      { key: 'security', label: 'Security' },
      { key: 'sessions', label: 'Sessions' },
    ],
  },
  {
    label: 'Workspace',
    permission: 'admin:workspace',
    items: [
      { key: 'workspace', label: 'General' },
      { key: 'ws-features', label: 'Features' },
      { key: 'ws-data', label: 'Data & AI' },
    ],
  },
  {
    label: 'Organization',
    permission: 'admin:org',
    items: [
      { key: 'organization', label: 'General' },
      { key: 'org-security', label: 'Security' },
      { key: 'org-billing', label: 'Billing' },
    ],
  },
  {
    label: 'Platform',
    permission: 'admin:platform',
    items: [
      { key: 'platform', label: 'Tenants' },
      { key: 'system-health', label: 'System health' },
    ],
  },
]
const visibleGroups = computed(() => groups.filter((g) => !g.permission || platform.can(g.permission)))
const section = computed(() => (route.params.section as string) || 'personal')
function go(key: string) {
  router.push(`/settings/${key}`)
}
function save() {
  ui.pushToast({ kind: 'success', title: 'Settings saved' })
}

const sessions = [
  { id: 's1', device: 'Chrome · Windows', location: 'Riyadh, SA', current: true, last: isoAgo(2) },
  { id: 's2', device: 'Safari · iPhone', location: 'Riyadh, SA', current: false, last: isoAgo(180) },
  { id: 's3', device: 'Edge · Windows', location: 'Dubai, AE', current: false, last: isoAgo(60 * 24 * 3) },
]
const notifPrefs = [
  { key: 'pipeline', label: 'Pipeline failures', on: true },
  { key: 'quality', label: 'Data quality incidents', on: true },
  { key: 'approvals', label: 'Approval requests', on: true },
  { key: 'digest', label: 'Weekly digest', on: false },
]
</script>

<template>
  <div class="settings">
    <aside class="settings__nav">
      <h1 class="settings__title">Settings</h1>
      <div v-for="g in visibleGroups" :key="g.label" class="settings__group">
        <div class="settings__group-label">{{ g.label }}</div>
        <button
          v-for="it in g.items"
          :key="it.key"
          class="settings__item"
          :class="{ 'is-active': section === it.key }"
          @click="go(it.key)"
        >
          {{ it.label }}
        </button>
      </div>
    </aside>

    <div class="settings__content">
      <!-- Profile -->
      <template v-if="section === 'personal'">
        <h2 class="settings__h">Profile</h2>
        <VipCard class="settings__form">
          <VipInput :model-value="platform.user.name" label="Full name" />
          <VipInput :model-value="platform.user.email" label="Email" type="email" readonly />
          <VipInput :model-value="platform.user.jobTitle" label="Job title" />
          <VipInput :model-value="platform.user.timezone" label="Time zone" />
          <VipButton variant="primary" @click="save">Save profile</VipButton>
        </VipCard>
      </template>

      <!-- Appearance -->
      <template v-else-if="section === 'appearance'">
        <h2 class="settings__h">Appearance</h2>
        <VipCard class="settings__form">
          <div>
            <label class="settings__label">Theme</label>
            <VipSegmented
              :model-value="theme.mode"
              :options="[
                { value: 'light', label: 'Light', icon: 'sun' },
                { value: 'dark', label: 'Dark', icon: 'moon' },
                { value: 'system', label: 'System', icon: 'monitor' },
              ]"
              @update:model-value="theme.setMode($event as ThemeMode)"
            />
          </div>
          <p class="settings__hint">Theme preference is saved to this browser and applied instantly.</p>
        </VipCard>
      </template>

      <!-- Notifications -->
      <template v-else-if="section === 'notifications'">
        <h2 class="settings__h">Notification preferences</h2>
        <VipCard class="settings__form">
          <div v-for="n in notifPrefs" :key="n.key" class="settings__row">
            <span>{{ n.label }}</span>
            <VipSwitch :model-value="n.on" @update:model-value="n.on = $event" />
          </div>
          <VipButton variant="primary" @click="save">Save preferences</VipButton>
        </VipCard>
      </template>

      <!-- Security -->
      <template v-else-if="section === 'security'">
        <h2 class="settings__h">Security</h2>
        <VipCard class="settings__form">
          <div class="settings__row">
            <span>Multi-factor authentication</span><VipBadge tone="success" size="sm">Enabled</VipBadge>
          </div>
          <div class="settings__row">
            <span>Password</span><VipButton variant="secondary" size="sm">Change</VipButton>
          </div>
          <p class="settings__hint">Authentication is enforced by the backend identity provider.</p>
        </VipCard>
      </template>

      <!-- Sessions -->
      <template v-else-if="section === 'sessions'">
        <h2 class="settings__h">Active sessions</h2>
        <VipCard>
          <div v-for="s in sessions" :key="s.id" class="settings__session">
            <VipIcon name="monitor" :size="18" />
            <div class="settings__session-info">
              <div>{{ s.device }} <VipBadge v-if="s.current" tone="brand" size="sm">This device</VipBadge></div>
              <div class="settings__session-meta">{{ s.location }} · {{ relativeTime(s.last) }}</div>
            </div>
            <VipButton
              v-if="!s.current"
              variant="ghost"
              size="sm"
              @click="ui.pushToast({ kind: 'info', title: 'Session revoked' })"
              >Revoke</VipButton
            >
          </div>
          <VipButton
            variant="danger"
            size="sm"
            style="margin-top: 12px"
            @click="ui.pushToast({ kind: 'warning', title: 'Signed out everywhere' })"
            >Sign out all other sessions</VipButton
          >
        </VipCard>
      </template>

      <!-- generic sections -->
      <template v-else>
        <h2 class="settings__h">{{ section.replace(/-/g, ' ') }}</h2>
        <VipCard class="settings__form">
          <p class="settings__hint">
            This settings section renders workspace / organization / platform controls appropriate to your role.
          </p>
          <div class="settings__row">
            <span>Section</span><VipBadge tone="neutral" size="sm">{{ section }}</VipBadge>
          </div>
          <VipButton variant="primary" @click="save">Save</VipButton>
        </VipCard>
      </template>
    </div>
  </div>
</template>

<style scoped>
.settings {
  display: flex;
  gap: var(--vip-sp-8);
  max-width: 1100px;
  margin: 0 auto;
  padding: var(--vip-sp-8) var(--vip-sp-9);
}
.settings__nav {
  width: 220px;
  flex: none;
}
.settings__title {
  font-size: var(--vip-fs-xl);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-6);
}
.settings__group {
  margin-bottom: var(--vip-sp-6);
}
.settings__group-label {
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-disabled);
  margin-bottom: var(--vip-sp-3);
}
.settings__item {
  display: block;
  width: 100%;
  text-align: left;
  padding: var(--vip-sp-3) var(--vip-sp-4);
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
.settings__item:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.settings__item.is-active {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  font-weight: var(--vip-fw-medium);
}
.settings__content {
  flex: 1;
  min-width: 0;
}
.settings__h {
  font-size: var(--vip-fs-xl);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-6);
  text-transform: capitalize;
}
.settings__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
  max-width: 520px;
}
.settings__label {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
  display: block;
  margin-bottom: var(--vip-sp-3);
}
.settings__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.settings__hint {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.settings__session {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.settings__session-info {
  flex: 1;
}
.settings__session-meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  margin-top: 2px;
}
</style>
