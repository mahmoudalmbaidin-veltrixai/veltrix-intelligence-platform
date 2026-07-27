<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import {
  connectionIcon,
  connectionService,
  CONNECTOR_STATUS,
  CONNECTOR_CATEGORY_LABEL,
  DEPLOYMENT_LABEL,
  type ConnectionType,
} from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const router = useRouter()
const search = ref('')
const category = ref('all')
const status = ref('all')
const deployment = ref('all')
const details = ref<ConnectionType | null>(null)

const { data: types, isLoading } = useQuery('connections:types', () => connectionService.types())

const categoryOptions = computed(() => {
  const present = new Set((types.value ?? []).map((t) => t.category))
  return [
    { value: 'all', label: 'All categories' },
    ...[...present].map((c) => ({ value: c, label: CONNECTOR_CATEGORY_LABEL[c] ?? c })),
  ]
})
const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'available', label: 'Available' },
  { value: 'beta', label: 'Beta' },
  { value: 'requires_driver', label: 'Requires driver' },
  { value: 'requires_agent', label: 'Requires agent' },
  { value: 'planned', label: 'Planned' },
]
const deploymentOptions = [
  { value: 'all', label: 'Any deployment' },
  { value: 'cloud', label: 'Cloud' },
  { value: 'on_prem', label: 'On-premise' },
  { value: 'hybrid', label: 'Cloud / on-premise' },
]

const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return (types.value ?? []).filter((item) => {
    const matchesQuery =
      !query ||
      `${item.name} ${item.vendor} ${item.category} ${item.subcategory} ${item.description}`
        .toLowerCase()
        .includes(query)
    const matchesCategory = category.value === 'all' || item.category === category.value
    const matchesStatus = status.value === 'all' || item.implementation_status === status.value
    const matchesDeployment =
      deployment.value === 'all' ||
      item.deployment === deployment.value ||
      (deployment.value !== 'hybrid' && item.deployment === 'hybrid')
    return matchesQuery && matchesCategory && matchesStatus && matchesDeployment
  })
})

const availableCount = computed(() => (types.value ?? []).filter((t) => t.is_enabled).length)

function presentation(item: ConnectionType) {
  return CONNECTOR_STATUS[item.implementation_status] ?? CONNECTOR_STATUS.planned
}
function isCreatable(item: ConnectionType): boolean {
  return item.is_enabled && Object.keys(item.configuration_schema.properties ?? {}).length > 0
}
function connect(item: ConnectionType) {
  if (item.key === 'local_file') {
    router.push('/datasets')
    return
  }
  router.push({ path: '/connections/new', query: { type: item.key } })
}
</script>

<template>
  <div class="catalog">
    <VipPageHeader
      title="Connector catalog"
      description="Browse the enterprise connector catalog. Status reflects true backend readiness."
    >
      <template #actions>
        <VipButton variant="tertiary" icon="chevronLeft" @click="router.push('/connections')">Back</VipButton>
      </template>
    </VipPageHeader>

    <div class="catalog__toolbar">
      <VipInput v-model="search" class="catalog__search" icon="search" placeholder="Search connectors, vendors…" />
      <VipSelect v-model="category" label="" :options="categoryOptions" />
      <VipSelect v-model="status" label="" :options="statusOptions" />
      <VipSelect v-model="deployment" label="" :options="deploymentOptions" />
    </div>
    <p class="catalog__count">
      Showing {{ filtered.length }} of {{ types?.length ?? 0 }} connectors · {{ availableCount }} available now
    </p>

    <div v-if="isLoading" class="catalog__loading">Loading connector catalog…</div>
    <div v-else-if="filtered.length" class="catalog__grid">
      <article v-for="item in filtered" :key="item.key" class="catalog__card">
        <div class="catalog__head">
          <span class="catalog__icon"><VipIcon :name="connectionIcon(item.key, item.category)" :size="20" /></span>
          <VipBadge :tone="presentation(item).tone" variant="soft" size="sm">{{ presentation(item).label }}</VipBadge>
        </div>
        <h3>{{ item.name }}</h3>
        <small class="catalog__vendor"
          >{{ item.vendor }} · {{ CONNECTOR_CATEGORY_LABEL[item.category] ?? item.category }}</small
        >
        <p class="catalog__desc">{{ item.description }}</p>
        <div class="catalog__meta">
          <span class="catalog__chip">{{ DEPLOYMENT_LABEL[item.deployment] ?? item.deployment }}</span>
          <span v-for="method in item.auth_methods.slice(0, 2)" :key="method" class="catalog__chip">{{
            method.replace(/_/g, ' ')
          }}</span>
        </div>
        <div class="catalog__actions">
          <VipButton v-if="isCreatable(item)" variant="primary" size="sm" @click="connect(item)"
            >Create connection</VipButton
          >
          <VipButton v-else-if="item.key === 'local_file'" variant="primary" size="sm" @click="connect(item)"
            >Upload in Datasets</VipButton
          >
          <VipButton variant="tertiary" size="sm" @click="details = item">View requirements</VipButton>
        </div>
      </article>
    </div>
    <VipEmptyState
      v-else
      icon="search"
      title="No connectors match"
      description="Try another search or clear the filters."
    />

    <VipDialog
      :open="!!details"
      :title="details?.name ?? ''"
      :description="
        details ? `${details.vendor} · ${CONNECTOR_CATEGORY_LABEL[details.category] ?? details.category}` : ''
      "
      @close="details = null"
    >
      <div v-if="details" class="req">
        <VipBadge :tone="presentation(details).tone" variant="soft" size="sm">{{
          presentation(details).label
        }}</VipBadge>
        <p class="req__desc">{{ details.description }}</p>

        <h4>Deployment</h4>
        <p>{{ DEPLOYMENT_LABEL[details.deployment] ?? details.deployment }}</p>

        <h4>Authentication methods</h4>
        <div class="req__chips">
          <span v-for="m in details.auth_methods" :key="m" class="catalog__chip">{{ m.replace(/_/g, ' ') }}</span>
          <span v-if="!details.auth_methods.length" class="req__muted">Not applicable</span>
        </div>

        <h4>Capabilities</h4>
        <div class="req__chips">
          <span v-for="cap in details.capabilities" :key="cap" class="catalog__chip">{{ cap.replace(/_/g, ' ') }}</span>
          <span v-if="!details.capabilities.length" class="req__muted">Defined once implemented</span>
        </div>

        <h4>Requirements &amp; network</h4>
        <ul v-if="details.requirements.length" class="req__list">
          <li v-for="(line, i) in details.requirements" :key="i">{{ line }}</li>
        </ul>
        <p v-else class="req__muted">No special setup documented yet.</p>

        <p
          v-if="details.implementation_status !== 'available' && details.implementation_status !== 'beta'"
          class="req__note"
        >
          This connector is catalog-defined but not yet operational. It is shown so you can plan integrations; creating
          a connection is disabled until it reaches Available.
        </p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="details = null">Close</VipButton>
        <VipButton v-if="details && isCreatable(details)" variant="primary" @click="details && connect(details)"
          >Create connection</VipButton
        >
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.catalog {
  max-width: 1280px;
  margin: 0 auto;
}
.catalog__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-3);
}
.catalog__search {
  width: min(320px, 100%);
}
.catalog__count {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  margin-bottom: var(--vip-sp-6);
}
.catalog__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--vip-sp-6);
}
.catalog__card {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-6);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
  background: var(--vip-surface-1);
}
.catalog__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.catalog__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-2);
  color: var(--vip-text-secondary);
}
.catalog__card h3 {
  margin: 0;
  font-size: var(--vip-fs-md);
}
.catalog__vendor,
.catalog__desc {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.catalog__desc {
  flex: 1;
}
.catalog__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-2);
}
.catalog__chip {
  font-size: var(--vip-fs-2xs);
  text-transform: capitalize;
  padding: 2px 8px;
  border-radius: var(--vip-radius-pill, 999px);
  background: var(--vip-surface-2);
  color: var(--vip-text-secondary);
  border: 1px solid var(--vip-border-subtle);
}
.catalog__actions {
  display: flex;
  gap: var(--vip-sp-3);
  margin-top: var(--vip-sp-2);
}
.catalog__loading {
  color: var(--vip-text-muted);
}
.req__desc {
  margin: var(--vip-sp-3) 0 var(--vip-sp-4);
}
.req h4 {
  margin: var(--vip-sp-4) 0 var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
}
.req__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-2);
}
.req__list {
  margin: 0;
  padding-left: var(--vip-sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
.req__muted {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.req__note {
  margin-top: var(--vip-sp-5);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
</style>
