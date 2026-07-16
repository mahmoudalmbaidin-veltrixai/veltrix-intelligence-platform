<script setup lang="ts">
import { ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { adminService, ASSIGNABLE_ROLES, type Member } from './admin.service'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAvatar from '@/shared/ui/VipAvatar.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const { data } = useQuery('admin:members', () => adminService.listMembers())
const members = ref<Member[]>([])
watch(data, (d) => { if (d) members.value = d }, { immediate: true })

const inviteOpen = ref(false)
const inviteEmail = ref('')
const inviteRole = ref(ASSIGNABLE_ROLES[6])

const columns: Column<Member>[] = [
  { key: 'name', label: 'Member' }, { key: 'role', label: 'Role' }, { key: 'status', label: 'Status' },
  { key: 'lastActive', label: 'Last active' }, { key: 'actions', label: '', align: 'right' },
]
const roleItems = ASSIGNABLE_ROLES.map((r) => ({ key: r, label: r }))
function changeRole(m: Member, role: string) { m.role = role; ui.pushToast({ kind: 'success', title: 'Role updated', message: `${m.name} → ${role}` }) }
function invite() {
  members.value.unshift({ id: `m_${Date.now()}`, name: inviteEmail.value.split('@')[0], email: inviteEmail.value, role: inviteRole.value, status: 'invited', lastActive: new Date().toISOString() })
  ui.pushToast({ kind: 'success', title: 'Invitation sent', message: inviteEmail.value })
  inviteOpen.value = false; inviteEmail.value = ''
}
function tone(s: Member['status']) { return s === 'active' ? 'success' : s === 'invited' ? 'info' : 'warning' }
</script>

<template>
  <div>
    <VipPageHeader title="Members & Roles" description="Manage organization membership and role assignments.">
      <template #actions><VipButton variant="primary" icon="plus" @click="inviteOpen = true">Invite member</VipButton></template>
    </VipPageHeader>
    <VipTable :columns="columns" :rows="members" :row-key="(r) => r.id">
      <template #cell-name="{ row }">
        <div class="mem"><VipAvatar :name="row.name" :size="30" /><div><div class="mem-name">{{ row.name }}</div><div class="mem-email">{{ row.email }}</div></div></div>
      </template>
      <template #cell-role="{ row }">
        <VipMenu :items="roleItems" align="start" @select="changeRole(row, $event)">
          <template #trigger><button class="mem-role"><VipBadge tone="brand" size="sm">{{ row.role }}</VipBadge></button></template>
        </VipMenu>
      </template>
      <template #cell-status="{ row }"><VipBadge :tone="tone(row.status)" size="sm">{{ row.status }}</VipBadge></template>
      <template #cell-lastActive="{ row }">{{ relativeTime(row.lastActive) }}</template>
      <template #cell-actions="{ row }"><VipButton variant="ghost" size="xs" icon="dotsV" @click="ui.pushToast({ kind: 'info', title: 'Member actions', message: row.name })" /></template>
    </VipTable>

    <VipDialog :open="inviteOpen" title="Invite member" @close="inviteOpen = false">
      <VipInput v-model="inviteEmail" label="Email address" type="email" placeholder="name@company.com" required />
      <div style="margin-top: 12px"><VipSelect v-model="inviteRole" label="Role" :options="ASSIGNABLE_ROLES.map((r) => ({ value: r, label: r }))" /></div>
      <template #footer>
        <VipButton variant="tertiary" @click="inviteOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :disabled="!inviteEmail" @click="invite">Send invite</VipButton>
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.mem { display: flex; align-items: center; gap: var(--vip-sp-4); }
.mem-name { font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.mem-email { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }
.mem-role { background: none; border: none; padding: 0; cursor: pointer; }
</style>
