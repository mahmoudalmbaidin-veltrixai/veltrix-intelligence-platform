<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { formatNumber } from '@/shared/lib/format'
import {
  marketplaceService,
  CATEGORY_ICON,
  type Extension,
  type ExtensionStatus,
} from './marketplace.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()

const id = computed(() => String(route.params.id))

const { data, isLoading } = useQuery(
  () => `marketplace:get:${id.value}`,
  (signal) =>
    marketplaceService.get(id.value).then((r) => {
      signal.throwIfAborted()
      return r
    }),
)

const extension = computed<Extension | undefined>(() => data.value)

const localStatus = ref<ExtensionStatus | null>(null)
watch(extension, (e) => {
  if (e && localStatus.value === null) localStatus.value = e.status
})
const status = computed<ExtensionStatus>(() => localStatus.value ?? extension.value?.status ?? 'available')

const STATUS_TONE: Record<ExtensionStatus, 'success' | 'brand' | 'info' | 'warning' | 'danger' | 'neutral'> = {
  installed: 'success',
  available: 'brand',
  beta: 'info',
  internal: 'neutral',
  'coming-soon': 'neutral',
  restricted: 'warning',
  incompatible: 'danger',
}
const STATUS_LABEL: Record<ExtensionStatus, string> = {
  installed: 'Installed',
  available: 'Available',
  beta: 'Beta',
  internal: 'Internal only',
  'coming-soon': 'Coming soon',
  restricted: 'Restricted',
  incompatible: 'Incompatible',
}

const canInstall = computed(() => status.value === 'available' || status.value === 'beta')

function install() {
  if (!extension.value) return
  localStatus.value = 'installed'
  ui.pushToast({ kind: 'success', title: 'Installed', message: `${extension.value.name} is now enabled.` })
}
function remove() {
  if (!extension.value) return
  localStatus.value = 'available'
  ui.pushToast({ kind: 'info', title: 'Removed', message: `${extension.value.name} has been uninstalled.` })
}
function requestAccess() {
  if (!extension.value) return
  ui.pushToast({ kind: 'info', title: 'Access requested', message: `${extension.value.name} requires governance approval.` })
}
</script>

<template>
  <div class="ext">
    <VipButton variant="ghost" size="sm" icon="chevronLeft" class="ext__back" @click="router.push('/marketplace')">
      Back to Marketplace
    </VipButton>

    <div v-if="isLoading" class="ext__loading"><VipSpinner :size="22" label="Loading extension…" /></div>

    <VipEmptyState
      v-else-if="!extension"
      icon="store"
      title="Extension not found"
      description="This extension may have been removed or is unavailable on your plan."
    >
      <VipButton variant="secondary" @click="router.push('/marketplace')">Back to Marketplace</VipButton>
    </VipEmptyState>

    <template v-else>
      <VipPageHeader :title="extension.name" :description="`by ${extension.author} · v${extension.version}`">
        <template #status>
          <VipBadge :tone="STATUS_TONE[status]" variant="soft" size="sm">{{ STATUS_LABEL[status] }}</VipBadge>
        </template>
        <template #actions>
          <VipButton v-if="status === 'installed'" variant="danger" icon="trash" @click="remove">Remove</VipButton>
          <VipButton v-else-if="status === 'restricted'" variant="primary" icon="lock" @click="requestAccess">Request access</VipButton>
          <VipButton v-else-if="canInstall" variant="primary" icon="download" @click="install">Install</VipButton>
          <VipButton v-else variant="secondary" disabled>Unavailable</VipButton>
        </template>
      </VipPageHeader>

      <VipAlert
        v-if="status === 'incompatible'"
        tone="danger"
        title="Incompatible with your deployment"
      >
        This extension requires {{ extension.compatibility }}. Upgrade the platform runtime to install it.
      </VipAlert>
      <VipAlert
        v-else-if="extension.dependencies && extension.dependencies.length"
        tone="warning"
        title="Dependencies required"
      >
        Installing this extension will also enable: {{ extension.dependencies.join(', ') }}.
      </VipAlert>

      <div class="ext__layout">
        <div class="ext__main">
          <VipCard>
            <span class="ext__hero-icon"><VipIcon :name="CATEGORY_ICON[extension.category]" :size="26" /></span>
            <h2 class="ext__heading">Overview</h2>
            <p class="ext__desc">{{ extension.description }}</p>
          </VipCard>

          <VipCard>
            <h2 class="ext__heading">Screenshots</h2>
            <div class="ext__shots">
              <div v-for="i in 3" :key="i" class="ext__shot">
                <VipIcon name="image" :size="22" />
                <span>Preview {{ i }}</span>
              </div>
            </div>
          </VipCard>

          <VipCard v-if="extension.permissions && extension.permissions.length">
            <h2 class="ext__heading">Required permissions</h2>
            <ul class="ext__perms">
              <li v-for="p in extension.permissions" :key="p">
                <VipIcon name="key" :size="14" />
                <code>{{ p }}</code>
              </li>
            </ul>
          </VipCard>
        </div>

        <aside class="ext__side">
          <VipCard>
            <h2 class="ext__heading">Details</h2>
            <dl class="ext__dl">
              <div class="ext__dl-row"><dt>Category</dt><dd>{{ extension.category }}</dd></div>
              <div class="ext__dl-row"><dt>Version</dt><dd>{{ extension.version }}</dd></div>
              <div class="ext__dl-row">
                <dt>Rating</dt>
                <dd class="ext__rating"><VipIcon name="star" :size="13" /> {{ extension.rating ? extension.rating.toFixed(1) : '—' }}</dd>
              </div>
              <div class="ext__dl-row"><dt>Installs</dt><dd>{{ formatNumber(extension.installs) }}</dd></div>
              <div class="ext__dl-row"><dt>Compatibility</dt><dd>{{ extension.compatibility ?? '—' }}</dd></div>
              <div class="ext__dl-row"><dt>Required plan</dt><dd>{{ extension.requiredPlan ?? 'Any' }}</dd></div>
            </dl>
          </VipCard>

          <VipCard v-if="extension.requiredPlan">
            <h2 class="ext__heading">Plan restriction</h2>
            <p class="ext__note">
              This extension is available on the <strong>{{ extension.requiredPlan }}</strong> plan and above.
            </p>
          </VipCard>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ext { max-width: 1100px; margin: 0 auto; }
.ext__back { margin-bottom: var(--vip-sp-4); }
.ext__loading { display: flex; justify-content: center; padding: var(--vip-sp-12); }
.ext__layout { display: grid; grid-template-columns: 1fr 320px; gap: var(--vip-sp-5); align-items: start; }
.ext__main { display: flex; flex-direction: column; gap: var(--vip-sp-5); min-width: 0; }
.ext__side { display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.ext__hero-icon {
  width: 52px; height: 52px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--vip-radius-lg);
  background: var(--vip-brand-soft); color: var(--vip-brand-text);
  margin-bottom: var(--vip-sp-4);
}
.ext__heading { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-4); }
.ext__desc { font-size: var(--vip-fs-md); color: var(--vip-text-secondary); line-height: var(--vip-lh-normal); }
.ext__shots { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--vip-sp-4); }
.ext__shot {
  aspect-ratio: 4 / 3;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--vip-sp-3);
  background: var(--vip-surface-2);
  border: 1px dashed var(--vip-border);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
}
.ext__perms { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.ext__perms li { display: flex; align-items: center; gap: var(--vip-sp-3); color: var(--vip-text-secondary); }
.ext__perms code { font-family: var(--vip-font-mono); font-size: var(--vip-fs-xs); }
.ext__dl { margin: 0; }
.ext__dl-row { display: flex; align-items: center; justify-content: space-between; padding: var(--vip-sp-4) 0; border-bottom: 1px solid var(--vip-border-subtle); }
.ext__dl-row:last-child { border-bottom: none; }
.ext__dl-row dt { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.ext__dl-row dd { margin: 0; font-size: var(--vip-fs-sm); color: var(--vip-text-primary); font-weight: var(--vip-fw-medium); }
.ext__rating { display: inline-flex; align-items: center; gap: 4px; color: var(--vip-warning-text); }
.ext__note { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
@media (max-width: 900px) {
  .ext__layout { grid-template-columns: 1fr; }
}
</style>
