<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { adminService, type InvitationRow, type Member } from './admin.service'
import type { RoleDto } from '@/shared/services/governance/apiGovernanceService'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { formatDateTime } from '@/shared/lib/format'
import { safeErrorText } from '@/shared/lib/safeError'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAvatar from '@/shared/ui/VipAvatar.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const platform = usePlatformStore()
const tenantKey = computed(() => platform.organization?.id ?? 'none')

const {
  data,
  error: queryError,
  isLoading,
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

const canInvite = computed(() => platform.can('organization.members.invite'))
const canUpdate = computed(() => platform.can('organization.members.update'))
const canRemove = computed(() => platform.can('organization.members.remove'))

// --- Member search ---
const search = ref('')
const filteredMembers = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return members.value
  return members.value.filter(
    (m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q) || m.role.toLowerCase().includes(q),
  )
})
const pendingInvites = computed(() => invitations.value.filter((i) => i.status === 'pending').length)

// --- Invite flow ---
const inviteOpen = ref(false)
const inviteEmail = ref('')
const inviteRole = ref('organization_member')
const assignableRoles = ref<RoleDto[]>([])
const inviteSubmitting = ref(false)
const inviteError = ref<string | null>(null)
const emailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inviteEmail.value.trim()))

onMounted(async () => {
  try {
    assignableRoles.value = await adminService.listAssignableOrganizationRoles()
    inviteRole.value = assignableRoles.value[0]?.key ?? 'organization_member'
  } catch {
    assignableRoles.value = []
  }
})

function openInvite() {
  inviteEmail.value = ''
  inviteError.value = null
  inviteRole.value = assignableRoles.value[0]?.key ?? 'organization_member'
  inviteOpen.value = true
}
async function submitInvite() {
  if (!emailValid.value || inviteSubmitting.value) return
  inviteSubmitting.value = true
  inviteError.value = null
  try {
    await adminService.inviteMember(inviteEmail.value.trim(), inviteRole.value)
    await Promise.all([refetch(), refetchInvitations()])
    ui.pushToast({
      kind: 'success',
      title: 'Invitation sent',
      message: `${inviteEmail.value.trim()} · ${roleName(inviteRole.value)}`,
    })
    inviteOpen.value = false
  } catch (e) {
    inviteError.value = safeErrorText(e)
  } finally {
    inviteSubmitting.value = false
  }
}

// --- Inline role change ---
const roleBusyId = ref<string | null>(null)
const roleItems = () => assignableRoles.value.map((role) => ({ key: role.key, label: role.name }))
function roleName(key: string) {
  return assignableRoles.value.find((r) => r.key === key)?.name ?? key
}
async function changeRole(member: Member, role: string) {
  if (role === member.role) return
  roleBusyId.value = member.id
  try {
    Object.assign(member, await adminService.updateMember(member.id, role))
    ui.pushToast({ kind: 'success', title: 'Role updated', message: `${member.name} → ${roleName(role)}` })
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Role update failed', message: safeErrorText(e) })
  } finally {
    roleBusyId.value = null
  }
}

// --- Remove member (confirmation) ---
const removeTarget = ref<Member | null>(null)
const removePending = ref(false)
const removeError = ref<string | null>(null)
function askRemove(member: Member) {
  removeError.value = null
  removeTarget.value = member
}
function closeRemove() {
  if (removePending.value) return
  removeTarget.value = null
  removeError.value = null
}
async function confirmRemove() {
  if (!removeTarget.value) return
  removePending.value = true
  removeError.value = null
  try {
    await adminService.removeMember(removeTarget.value.id)
    ui.pushToast({ kind: 'success', title: 'Member removed', message: removeTarget.value.name })
    removeTarget.value = null
    await refetch()
  } catch (e) {
    removeError.value = safeErrorText(e)
  } finally {
    removePending.value = false
  }
}

// --- Revoke invitation (confirmation) ---
const revokeTarget = ref<InvitationRow | null>(null)
const revokePending = ref(false)
const revokeError = ref<string | null>(null)
function askRevoke(invitation: InvitationRow) {
  revokeError.value = null
  revokeTarget.value = invitation
}
function closeRevoke() {
  if (revokePending.value) return
  revokeTarget.value = null
  revokeError.value = null
}
async function confirmRevoke() {
  if (!revokeTarget.value) return
  revokePending.value = true
  revokeError.value = null
  try {
    await adminService.revokeInvitation(revokeTarget.value.id)
    ui.pushToast({ kind: 'success', title: 'Invitation revoked', message: revokeTarget.value.email })
    revokeTarget.value = null
    await refetchInvitations()
  } catch (e) {
    revokeError.value = safeErrorText(e)
  } finally {
    revokePending.value = false
  }
}

function rowMenu() {
  return canRemove.value ? [{ key: 'remove', label: 'Remove from organization', icon: 'trash', danger: true }] : []
}

const columns = computed<Column<Member>[]>(() => [
  { key: 'name', label: 'Member' },
  { key: 'role', label: 'Role' },
  { key: 'status', label: 'Status' },
  ...(canRemove.value ? [{ key: 'actions', label: '', align: 'right' as const }] : []),
])
const invitationColumns: Column<InvitationRow>[] = [
  { key: 'email', label: 'Invited email' },
  { key: 'organizationRole', label: 'Organization role' },
  { key: 'status', label: 'Status' },
  { key: 'expiresAt', label: 'Expires' },
  { key: 'actions', label: '', align: 'right' },
]
function tone(s: Member['status']) {
  return s === 'active' ? 'success' : s === 'invited' ? 'info' : 'warning'
}
</script>

<template>
  <div>
    <VipPageHeader title="Members & Roles" description="Manage who belongs to this organization and what they can do.">
      <template #actions>
        <VipButton v-if="canInvite" variant="primary" icon="plus" @click="openInvite">Invite member</VipButton>
      </template>
    </VipPageHeader>

    <VipAlert v-if="queryError" tone="danger" title="Members unavailable">
      The member list could not be loaded. Check your connection and permissions, then retry.
    </VipAlert>

    <div class="mem-toolbar">
      <VipInput v-model="search" icon="search" size="sm" placeholder="Search members by name, email or role" />
      <span class="mem-count">
        {{ filteredMembers.length }} of {{ members.length }} member{{ members.length === 1 ? '' : 's' }}
        <template v-if="pendingInvites">
          · {{ pendingInvites }} pending invite{{ pendingInvites === 1 ? '' : 's' }}</template
        >
      </span>
    </div>

    <VipTable
      :columns="columns"
      :rows="filteredMembers"
      :row-key="(r) => r.id"
      :loading="isLoading"
      empty-title="No members match"
      empty-description="Adjust your search, or invite someone to this organization."
    >
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
        <VipMenu v-if="canUpdate" :items="roleItems()" align="start" @select="changeRole(row, $event)">
          <template #trigger>
            <button class="mem-role" :disabled="roleBusyId === row.id" :aria-label="`Change role for ${row.name}`">
              <VipBadge tone="brand" size="sm">{{ roleName(row.role) }}</VipBadge>
              <VipIcon name="chevronDown" :size="13" />
            </button>
          </template>
        </VipMenu>
        <VipBadge v-else tone="brand" size="sm">{{ roleName(row.role) }}</VipBadge>
      </template>
      <template #cell-status="{ row }">
        <VipBadge :tone="tone(row.status)" size="sm">{{ row.status }}</VipBadge>
      </template>
      <template #cell-actions="{ row }">
        <div class="mem-actions">
          <VipMenu :items="rowMenu()" align="end" @select="(k) => k === 'remove' && askRemove(row)">
            <template #trigger>
              <button class="mem-menu" :aria-label="`Actions for ${row.name}`">
                <VipIcon name="dotsV" :size="16" />
              </button>
            </template>
          </VipMenu>
        </div>
      </template>
    </VipTable>

    <section class="mem-invitations">
      <h2>Pending &amp; recent invitations</h2>
      <VipAlert v-if="invitationQueryError" tone="danger" title="Invitations unavailable">
        The invitation list could not be loaded.
      </VipAlert>
      <VipTable
        :columns="invitationColumns"
        :rows="invitations"
        :row-key="(invitation) => invitation.id"
        empty-title="No invitations"
        empty-description="Invite a teammate and their pending invitation will appear here."
      >
        <template #cell-organizationRole="{ row }">
          <VipBadge tone="brand" size="sm">{{ roleName(row.organizationRole) }}</VipBadge>
        </template>
        <template #cell-status="{ row }">
          <VipBadge :tone="row.status === 'pending' ? 'info' : 'neutral'" size="sm">{{ row.status }}</VipBadge>
        </template>
        <template #cell-expiresAt="{ row }">{{ formatDateTime(row.expiresAt) }}</template>
        <template #cell-actions="{ row }">
          <VipButton
            v-if="row.status === 'pending' && canInvite"
            variant="ghost"
            size="xs"
            icon="close"
            @click="askRevoke(row)"
          >
            Revoke
          </VipButton>
        </template>
      </VipTable>
    </section>

    <!-- Invite member -->
    <VipDialog
      :open="inviteOpen"
      title="Invite member"
      size="sm"
      :closable="!inviteSubmitting"
      @close="inviteOpen = false"
    >
      <div class="mem-invite">
        <VipInput
          v-model="inviteEmail"
          label="Work email"
          type="email"
          autocomplete="off"
          placeholder="name@company.com"
          :disabled="inviteSubmitting"
          required
          @enter="submitInvite"
        />
        <VipSelect
          v-model="inviteRole"
          label="Organization role"
          :disabled="inviteSubmitting"
          :options="assignableRoles.map((role) => ({ value: role.key, label: role.name }))"
        />
        <p class="mem-invite__hint">They’ll receive an invitation to join this organization with the selected role.</p>
        <VipAlert v-if="inviteError" tone="danger" title="Invitation failed">{{ inviteError }}</VipAlert>
      </div>
      <template #footer>
        <VipButton variant="tertiary" :disabled="inviteSubmitting" @click="inviteOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="inviteSubmitting" :disabled="!emailValid" @click="submitInvite">
          Send invitation
        </VipButton>
      </template>
    </VipDialog>

    <!-- Remove member -->
    <VipConfirmDialog
      :open="!!removeTarget"
      level="danger"
      title="Remove member?"
      :resource-name="removeTarget?.name"
      message="This person will immediately lose access to this organization and all of its workspaces."
      :impact="
        [
          removeTarget ? `Email: ${removeTarget.email}` : '',
          removeTarget ? `Current role: ${roleName(removeTarget.role)}` : '',
          'Their content ownership is handled per backend policy; they can be re-invited later.',
        ].filter(Boolean)
      "
      confirm-label="Remove member"
      :pending="removePending"
      :error="removeError"
      @confirm="confirmRemove"
      @cancel="closeRemove"
    />

    <!-- Revoke invitation -->
    <VipConfirmDialog
      :open="!!revokeTarget"
      level="warning"
      title="Revoke invitation?"
      :resource-name="revokeTarget?.email"
      message="The invitation link will stop working and the invitee will not be able to join with it."
      confirm-label="Revoke invitation"
      :pending="revokePending"
      :error="revokeError"
      @confirm="confirmRevoke"
      @cancel="closeRevoke"
    />
  </div>
</template>

<style scoped>
.mem-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-5);
  flex-wrap: wrap;
}
.mem-toolbar > *:first-child {
  width: min(360px, 100%);
}
.mem-count {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  white-space: nowrap;
}
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
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  background: none;
  border: none;
  padding: 2px 4px;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
  cursor: pointer;
}
.mem-role:hover:not(:disabled) {
  background: var(--vip-surface-hover);
}
.mem-actions {
  display: flex;
  justify-content: flex-end;
}
.mem-menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--vip-text-secondary);
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-md);
}
.mem-menu:hover {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border);
  color: var(--vip-text-primary);
}
.mem-invitations {
  margin-top: var(--vip-sp-8);
}
.mem-invitations h2 {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-4);
}
.mem-invite {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.mem-invite__hint {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
</style>
