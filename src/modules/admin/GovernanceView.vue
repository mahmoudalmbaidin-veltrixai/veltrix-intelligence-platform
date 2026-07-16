<script setup lang="ts">
import { ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { adminService, type Policy } from './admin.service'
import { useUiStore } from '@/shared/stores/ui'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'

const ui = useUiStore()
const { data } = useQuery('admin:policies', () => adminService.listPolicies())
const policies = ref<Policy[]>([])
watch(data, (d) => { if (d) policies.value = d }, { immediate: true })
function save() { ui.pushToast({ kind: 'success', title: 'Governance policies saved' }) }
</script>

<template>
  <div>
    <VipPageHeader title="Governance Policies" description="Organization-wide security, retention and data-handling controls.">
      <template #actions><VipButton variant="primary" icon="save" @click="save">Save policies</VipButton></template>
    </VipPageHeader>
    <div class="gov">
      <VipCard v-for="p in policies" :key="p.key" class="gov-row">
        <div class="gov-info">
          <div class="gov-name">{{ p.label }}</div>
          <p class="gov-desc">{{ p.description }}</p>
        </div>
        <div class="gov-control">
          <VipSwitch v-if="typeof p.value === 'boolean'" :model-value="p.value" @update:model-value="p.value = $event" />
          <VipInput v-else :model-value="p.value" size="sm" @update:model-value="p.value = String($event)" />
        </div>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.gov { display: flex; flex-direction: column; gap: var(--vip-sp-4); max-width: 820px; }
.gov-row { display: flex; align-items: center; justify-content: space-between; gap: var(--vip-sp-6); }
.gov-info { flex: 1; }
.gov-name { font-weight: var(--vip-fw-semibold); }
.gov-desc { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); margin-top: var(--vip-sp-2); }
.gov-control { min-width: 240px; display: flex; justify-content: flex-end; }
.gov-control :deep(.vip-field) { width: 100%; }
</style>
