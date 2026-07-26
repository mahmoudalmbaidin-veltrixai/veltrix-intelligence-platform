<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { adminService, type InvitationRow, type Member } from './admin.service'
import type { RoleDto } from '@/shared/services/governance/apiGovernanceService'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { formatDateTime } from '@/shared/lib/format'
import VipAlert from '@/shared/ui/VipAlert.vue'
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
const platform = usePlatformStore()
const tenantKey = computed(() => platform.organization?.id ?? 'none')
const {
  data,
  error: queryError,
  refetch,
} = useQuery(
  () => `admin:${tenantKey.value}:members`,
  () => adminService.listMembers(),
)
const members = ref<Member[]>([])
watch(
  data,
  (d) => {
    if (d) members.value = d
  },
  { immediate: true },
)
const {
  data: invitationData,
  error: invitationQueryError,
  refetch: refetchInvitations,
} = useQuery(
  () => `admin:${tenantKey.value}:invitations`,
  () => adminService.listInvitations(),
)
const invitations = ref<InvitationRow[]>([])
watch(invitationData, (value) => (invitations.value = value ?? []), { immediate: true })

const inviteOpen = ref(false)
const inviteEmail = ref('')
const inviteRole = ref('organization_member')
const assignableRoles = ref<RoleDto[]>([])
const submitting = ref(false)
const mutationError = ref('')

onMounted(async () => {
  assignableRoles.value = await adminService.listAssignableOrganizationRoles()
  inviteRole.value = assignableRoles.value[0]?.key ?? 'organization_member'
})

const columns: Column<Member>[] = [
  { key: 'name', label: 'Member' },
  { key: 'role', label: 'Role' },
  { key: 'status', label: 'Status' },
]
const invitationColumns: Column<InvitationRow>[] = [
  { key: 'email', label: 'Invited email' },
  { key: 'organizationRole', label: 'Organization role' },
  { key: 'status', label: 'Status' },
  { key: 'expiresAt', label: 'Expires' },
  { key: 'actions', label: '', align: 'right' },
]
const roleItems = () => assignableRoles.value.map((role) => ({ key: role.key, label: role.name }))
async function changeRole(member: Member, role: string) {
  submitting.value = true
  mutationError.value = ''
  try {
    Object.assign(member, await adminService.updateMember(member.id, role))
    ui.pushToast({ kind: 'success', title: 'Role updated', message: `${member.name}: ${role}` })
  } catch {
    mutationError.value = 'The role could not be updated. Owner and self-escalation protections may apply.'
  } finally {
    submitting.value = false
  }
}
async function invite() {
  submitting.value = true
  mutationError.value = ''
  try {
    await adminService.inviteMember(inviteEmail.value, inviteRole.value)
    await Promise.all([refetch(), refetchInvitations()])
    ui.pushToast({
      kind: 'success',
      title: 'Invitation created',
      message: 'Email delivery is not configured in local development.',
    })
    inviteOpen.value = false
    inviteEmail.value = ''
  } catch {
    mutationError.value = 'The invitation could not be created. Check the email, role, and existing invitations.'
  } finally {
    submitting.value = false
  }
}
async function revokeInvitation(invitation: InvitationRow) {
  submitting.value = true
  mutationError.value = ''
  try {
    await adminService.revokeInvitation(invitation.id)
    await refetchInvitations()
    ui.pushToast({ kind: 'success', title: 'Invitation revoked', message: invitation.email })
  } catch {
    mutationError.value = 'The invitation could not be revoked.'
  } finally {
    submitting.value = false
  }
}
function tone(s: Member['status']) {
  return s === 'active' ? 'success' : s === 'invited' ? 'info' : 'warning'
}
</script>

<template>
  <div>
    <VipPageHeader title="Members & Roles" description="Manage organization membership and role assignments.">
      <template #actions
        ><VipButton
          v-if="platform.can('organization.members.invite')"
          variant="primary"
          icon="plus"
          @click="inviteOpen = true"
          >Invite member</VipButton
        ></template
      >
    </VipPageHeader>
    <VipAlert v-if="mutationError" tone="danger" title="Member operation failed">{{ mutationError }}</VipAlert>
    <VipAlert v-if="queryError" tone="danger" title="Members unavailable"
      >The member list could not be loaded.</VipAlert
    >
    <VipTable :columns="columns" :rows="members" :row-key="(r) => r.id">
      <template #cell-name="{ row }">
        <div class="mem">
          <VipAvatar :name="row.name" :size="30" />
          <div>
            <div class="mem-name">{{ row.name }}</div>
            <div class="mem-email">{{ row.email }}</div>
          </div>
        </div>
      </template>
      <template #cell-role="{ row }">
        <VipMenu
          v-if="platform.can('organization.members.update')"
          :items="roleItems()"
          align="start"
          @select="changeRole(row, $event)"
        >
          <template #trigger
            ><button class="mem-role" :disabled="submitting">
              <VipBadge tone="brand" size="sm">{{ row.role }}</VipBadge>
            </button></template
          >
        </VipMenu>
        <VipBadge v-else tone="brand" size="sm">{{ row.role }}</VipBadge>
      </template>
      <template #cell-status="{ row }"
        ><VipBadge :tone="tone(row.status)" size="sm">{{ row.status }}</VipBadge></template
      >
    </VipTable>

    <section class="mem-invitations">
      <h2>Invitations</h2>
      <VipAlert v-if="invitationQueryError" tone="danger" title="Invitations unavailable">
        The persisted invitation list could not be loaded.
      </VipAlert>
      <VipTable
        :columns="invitationColumns"
        :rows="invitations"
        :row-key="(invitation) => invitation.id"
        empty-title="No invitations"
        empty-description="Pending and historical invitations will appear here."
      >
        <template #cell-organizationRole="{ row }">
          <VipBadge tone="brand" size="sm">{{ row.organizationRole }}</VipBadge>
        </template>
        <template #cell-status="{ row }">
          <VipBadge :tone="row.status === 'pending' ? 'info' : 'neutral'" size="sm">{{ row.status }}</VipBadge>
        </template>
        <template #cell-expiresAt="{ row }">{{ formatDateTime(row.expiresAt) }}</template>
        <template #cell-actions="{ row }">
          <VipButton
            v-if="row.status === 'pending' && platform.can('organization.members.invite')"
            variant="danger"
            size="xs"
            :disabled="submitting"
            @click="revokeInvitation(row)"
          >
            Revoke
          </VipButton>
        </template>
      </VipTable>
    </section>

    <VipDialog :open="inviteOpen" title="Invite member" @close="inviteOpen = false">
      <VipInput v-model="inviteEmail" label="Email address" type="email" placeholder="name@company.com" required />
      <div style="margin-top: 12px">
        <VipSelect
          v-model="inviteRole"
          label="Role"
          :options="assignableRoles.map((role) => ({ value: role.key, label: role.name }))"
        />
      </div>
      <template #footer>
        <VipButton variant="tertiary" :disabled="submitting" @click="inviteOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="submitting" :disabled="!inviteEmail" @click="invite"
          >Create invitation</VipButton
        >
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.mem {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.mem-name {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.mem-email {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.mem-role {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
}
.mem-invitations {
  margin-top: var(--vip-sp-8);
}
.mem-invitations h2 {
  margin-bottom: var(--vip-sp-4);
}
</style>
