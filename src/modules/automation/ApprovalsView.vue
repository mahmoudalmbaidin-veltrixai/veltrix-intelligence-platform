<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { automationService, type Approval } from './automation.service'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const ui = useUiStore()
const { data } = useQuery('automation:approvals', () => automationService.listApprovals())
const local = ref<Approval[]>([])
watch(
  data,
  (d) => {
    if (d) local.value = d.map((a) => ({ ...a }))
  },
  { immediate: true },
)

const tab = ref<'pending' | 'decided'>('pending')
const list = computed(() =>
  local.value.filter((a) => (tab.value === 'pending' ? a.status === 'pending' : a.status !== 'pending')),
)

function decide(a: Approval, status: 'approved' | 'rejected') {
  a.status = status
  ui.pushToast({
    kind: status === 'approved' ? 'success' : 'warning',
    title: status === 'approved' ? 'Approved' : 'Rejected',
    message: a.title,
  })
}
function tone(s: Approval['status']) {
  return s === 'approved' ? 'success' : s === 'rejected' ? 'danger' : 'warning'
}
</script>

<template>
  <div class="apr">
    <VipPageHeader title="Approvals" description="Human sign-off gates raised by automations and workflows.">
      <template #actions>
        <VipSegmented
          v-model="tab"
          :options="[
            { value: 'pending', label: 'Pending' },
            { value: 'decided', label: 'Decided' },
          ]"
          size="sm"
        />
      </template>
    </VipPageHeader>

    <div v-if="list.length" class="apr-list">
      <VipCard v-for="a in list" :key="a.id" class="apr-card">
        <div class="apr-head">
          <div class="apr-title">{{ a.title }}</div>
          <VipBadge :tone="tone(a.status)" size="sm">{{ a.status }}</VipBadge>
        </div>
        <p class="apr-ctx">{{ a.context }}</p>
        <div class="apr-foot">
          <span class="apr-meta">Requested by {{ a.requestedBy }} · {{ relativeTime(a.requestedAt) }}</span>
          <div v-if="a.status === 'pending'" class="apr-actions">
            <VipButton variant="danger" size="sm" icon="close" @click="decide(a, 'rejected')">Reject</VipButton>
            <VipButton variant="primary" size="sm" icon="check" @click="decide(a, 'approved')">Approve</VipButton>
          </div>
        </div>
      </VipCard>
    </div>
    <VipEmptyState
      v-else
      icon="check"
      title="Nothing here"
      :description="tab === 'pending' ? 'No approvals awaiting your decision.' : 'No decided approvals yet.'"
    />
  </div>
</template>

<style scoped>
.apr-list {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
  max-width: 900px;
}
.apr-card {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.apr-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
}
.apr-title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.apr-ctx {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.apr-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
}
.apr-meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
}
.apr-actions {
  display: flex;
  gap: var(--vip-sp-3);
}
</style>
