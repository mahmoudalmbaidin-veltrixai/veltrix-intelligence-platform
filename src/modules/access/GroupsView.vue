<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { accessService, type Group, type GroupMember, type Principal } from './access.service'
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
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const platform = usePlatformStore()
const tenantKey = computed(() => platform.organization?.id ?? 'none')

const includeArchived = ref(false)
const {
  data,
  error: queryError,
  isLoading,
  refetch,
} = useQuery(
  () => `access:${tenantKey.value}:groups:${includeArchived.value}`,
  () => accessService.listGroups(includeArchived.value),
)
const groups = ref<Group[]>([])
watch(data, (d) => (groups.value = d ?? []), { immediate: true })

const canCreate = computed(() => platform.can('group.create'))
const canUpdate = computed(() => platform.can('group.update'))
const canDelete = computed(() => platform.can('group.delete'))
const canManageMembers = computed(() => platform.can('group.members.manage'))

const search = ref('')
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return groups.value
  return groups.value.filter((g) => g.name.toLowerCase().includes(q) || g.description.toLowerCase().includes(q))
})

const columns = computed<Column<Group>[]>(() => [
  { key: 'name', label: 'Group' },
  { key: 'member_count', label: 'Members' },
  { key: 'status', label: 'Status' },
  { key: 'updated_at', label: 'Updated' },
  { key: 'actions', label: '', align: 'right' as const },
])

// --- create / edit ---
const editOpen = ref(false)
const editTarget = ref<Group | null>(null)
const formName = ref('')
const formDescription = ref('')
const formSubmitting = ref(false)
const formError = ref<string | null>(null)
const formValid = computed(() => formName.value.trim().length >= 2)

function openCreate() {
  editTarget.value = null
  formName.value = ''
  formDescription.value = ''
  formError.value = null
  editOpen.value = true
}
function openEdit(group: Group) {
  editTarget.value = group
  formName.value = group.name
  formDescription.value = group.description
  formError.value = null
  editOpen.value = true
}
async function submitForm() {
  if (!formValid.value || formSubmitting.value) return
  formSubmitting.value = true
  formError.value = null
  try {
    if (editTarget.value) {
      await accessService.updateGroup(editTarget.value.id, editTarget.value.row_version, {
        name: formName.value.trim(),
        description: formDescription.value.trim(),
      })
      ui.pushToast({ kind: 'success', title: 'Group updated', message: formName.value.trim() })
    } else {
      await accessService.createGroup(formName.value.trim(), formDescription.value.trim())
      ui.pushToast({ kind: 'success', title: 'Group created', message: formName.value.trim() })
    }
    editOpen.value = false
    await refetch()
  } catch (e) {
    formError.value = safeErrorText(e)
  } finally {
    formSubmitting.value = false
  }
}

async function toggleArchive(group: Group) {
  try {
    await accessService.archiveGroup(group.id, group.row_version, !group.archived_at)
    ui.pushToast({
      kind: 'success',
      title: group.archived_at ? 'Group restored' : 'Group archived',
      message: group.name,
    })
    await refetch()
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Action failed', message: safeErrorText(e) })
  }
}

// --- delete ---
const deleteTarget = ref<Group | null>(null)
const deletePending = ref(false)
const deleteError = ref<string | null>(null)
async function confirmDelete() {
  if (!deleteTarget.value) return
  deletePending.value = true
  deleteError.value = null
  try {
    await accessService.deleteGroup(deleteTarget.value.id, deleteTarget.value.row_version)
    ui.pushToast({ kind: 'success', title: 'Group deleted', message: deleteTarget.value.name })
    deleteTarget.value = null
    await refetch()
  } catch (e) {
    deleteError.value = safeErrorText(e)
  } finally {
    deletePending.value = false
  }
}

// --- members ---
const membersOpen = ref(false)
const membersGroup = ref<Group | null>(null)
const members = ref<GroupMember[]>([])
const membersLoading = ref(false)
const membersError = ref<string | null>(null)
const availableMembers = ref<Principal[]>([])
const availableLoading = ref(false)
const availableError = ref<string | null>(null)
const memberQuery = ref('')

const filteredAvailable = computed(() => {
  const existing = new Set(members.value.map((m) => m.user_id))
  const q = memberQuery.value.trim().toLowerCase()
  return availableMembers.value.filter((p) => {
    if (p.principal_type !== 'user' || existing.has(p.id)) return false
    if (!q) return true
    return p.label.toLowerCase().includes(q) || (p.detail ?? '').toLowerCase().includes(q)
  })
})

async function openMembers(group: Group) {
  membersGroup.value = group
  membersOpen.value = true
  memberQuery.value = ''
  availableError.value = null
  await Promise.all([loadMembers(), loadAvailableMembers()])
}
async function loadMembers() {
  if (!membersGroup.value) return
  membersLoading.value = true
  membersError.value = null
  try {
    members.value = await accessService.listMembers(membersGroup.value.id)
  } catch (e) {
    membersError.value = safeErrorText(e)
  } finally {
    membersLoading.value = false
  }
}
async function loadAvailableMembers() {
  availableLoading.value = true
  availableError.value = null
  try {
    // Empty query returns active organization members (backend supports this).
    const all = await accessService.searchPrincipals('')
    availableMembers.value = all.filter((p) => p.principal_type === 'user')
  } catch (e) {
    availableMembers.value = []
    availableError.value = safeErrorText(e)
  } finally {
    availableLoading.value = false
  }
}
async function addMember(principal: Principal) {
  if (!membersGroup.value) return
  try {
    await accessService.addMember(membersGroup.value.id, principal.id)
    ui.pushToast({ kind: 'success', title: 'Member added', message: principal.label })
    memberQuery.value = ''
    await Promise.all([loadMembers(), refetch()])
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Could not add member', message: safeErrorText(e) })
  }
}
async function removeMember(member: GroupMember) {
  if (!membersGroup.value) return
  try {
    await accessService.removeMember(membersGroup.value.id, member.user_id)
    ui.pushToast({ kind: 'success', title: 'Member removed', message: member.display_name })
    await Promise.all([loadMembers(), refetch()])
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Could not remove member', message: safeErrorText(e) })
  }
}

function rowMenu(group: Group) {
  const items: { key: string; label: string; icon?: string; danger?: boolean }[] = []
  if (canManageMembers.value) items.push({ key: 'members', label: 'Manage members', icon: 'users' })
  if (canUpdate.value) {
    items.push({ key: 'edit', label: 'Rename', icon: 'text' })
    items.push({
      key: 'archive',
      label: group.archived_at ? 'Restore' : 'Archive',
      icon: group.archived_at ? 'refresh' : 'folder',
    })
  }
  if (canDelete.value) items.push({ key: 'delete', label: 'Delete', icon: 'trash', danger: true })
  return items
}
function onRowAction(group: Group, key: string) {
  if (key === 'members') void openMembers(group)
  else if (key === 'edit') openEdit(group)
  else if (key === 'archive') void toggleArchive(group)
  else if (key === 'delete') {
    deleteError.value = null
    deleteTarget.value = group
  }
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Groups & Teams"
      description="Organize members into teams. Groups can be granted roles and resource permissions."
    >
      <template #actions>
        <VipButton v-if="canCreate" variant="primary" icon="plus" @click="openCreate">New group</VipButton>
      </template>
    </VipPageHeader>

    <VipAlert v-if="queryError" tone="danger" title="Groups unavailable">
      The group list could not be loaded. Check your connection and permissions, then retry.
    </VipAlert>

    <div class="grp-toolbar">
      <VipInput v-model="search" icon="search" size="sm" placeholder="Search groups" />
      <label class="grp-archived">
        <input v-model="includeArchived" type="checkbox" />
        Show archived
      </label>
    </div>

    <VipTable
      :columns="columns"
      :rows="filtered"
      :row-key="(r) => r.id"
      :loading="isLoading"
      empty-title="No groups yet"
      empty-description="Create a group to manage access for a team all at once."
    >
      <template #cell-name="{ row }">
        <div class="grp">
          <VipAvatar :name="row.name" :size="30" />
          <div>
            <div class="grp-name">{{ row.name }}</div>
            <div v-if="row.description" class="grp-desc">{{ row.description }}</div>
          </div>
        </div>
      </template>
      <template #cell-member_count="{ row }">
        <VipBadge tone="neutral" size="sm">{{ row.member_count }}</VipBadge>
      </template>
      <template #cell-status="{ row }">
        <VipBadge :tone="row.archived_at ? 'warning' : 'success'" size="sm">
          {{ row.archived_at ? 'archived' : 'active' }}
        </VipBadge>
      </template>
      <template #cell-updated_at="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      <template #cell-actions="{ row }">
        <div class="grp-actions">
          <VipMenu :items="rowMenu(row)" align="end" @select="(k) => onRowAction(row, k)">
            <template #trigger>
              <button class="grp-menu" :aria-label="`Actions for ${row.name}`">
                <VipIcon name="dotsV" :size="16" />
              </button>
            </template>
          </VipMenu>
        </div>
      </template>
    </VipTable>

    <!-- Create / edit -->
    <VipDialog
      :open="editOpen"
      :title="editTarget ? 'Rename group' : 'New group'"
      size="sm"
      :closable="!formSubmitting"
      @close="editOpen = false"
    >
      <div class="grp-form">
        <VipInput v-model="formName" label="Group name" placeholder="e.g. Data Platform" required @enter="submitForm" />
        <VipInput v-model="formDescription" label="Description" placeholder="Optional summary" />
        <VipAlert v-if="formError" tone="danger" title="Could not save">{{ formError }}</VipAlert>
      </div>
      <template #footer>
        <VipButton variant="tertiary" :disabled="formSubmitting" @click="editOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="formSubmitting" :disabled="!formValid" @click="submitForm">
          {{ editTarget ? 'Save changes' : 'Create group' }}
        </VipButton>
      </template>
    </VipDialog>

    <!-- Members -->
    <VipDialog
      :open="membersOpen"
      :title="membersGroup ? `Members · ${membersGroup.name}` : 'Members'"
      size="md"
      @close="membersOpen = false"
    >
      <div class="grp-members">
        <section class="grp-section" aria-labelledby="grp-current-heading">
          <h3 id="grp-current-heading" class="grp-section__title">
            In this group
            <span class="grp-section__count">({{ members.length }})</span>
          </h3>
          <VipAlert v-if="membersError" tone="danger" title="Could not load members">{{ membersError }}</VipAlert>
          <p v-if="membersLoading" class="grp-empty">Loading current members…</p>
          <p v-else-if="!members.length" class="grp-empty">No members in this group yet.</p>
          <ul v-else class="grp-member-list">
            <li v-for="m in members" :key="m.user_id" class="grp-member">
              <VipAvatar :name="m.display_name" :size="30" />
              <div class="grp-member__text">
                <div class="grp-member__name">{{ m.display_name }}</div>
                <div class="grp-member__email">{{ m.email ?? m.username }}</div>
              </div>
              <button
                v-if="canManageMembers"
                class="grp-menu"
                :aria-label="`Remove ${m.display_name}`"
                @click="removeMember(m)"
              >
                <VipIcon name="close" :size="15" />
              </button>
            </li>
          </ul>
        </section>

        <section v-if="canManageMembers" class="grp-section" aria-labelledby="grp-available-heading">
          <h3 id="grp-available-heading" class="grp-section__title">
            Organization members
            <span class="grp-section__count">({{ filteredAvailable.length }} available)</span>
          </h3>
          <VipInput v-model="memberQuery" icon="search" placeholder="Filter by name or email" autocomplete="off" />
          <VipAlert v-if="availableError" tone="danger" title="Could not load organization members">
            {{ availableError }}
          </VipAlert>
          <p v-if="availableLoading" class="grp-empty">Loading organization members…</p>
          <p v-else-if="!filteredAvailable.length" class="grp-empty">
            {{
              memberQuery.trim()
                ? 'No matching organization members.'
                : 'Everyone in the organization is already in this group.'
            }}
          </p>
          <ul v-else class="grp-member-list grp-member-list--available">
            <li v-for="p in filteredAvailable" :key="p.id">
              <button type="button" class="grp-result" @click="addMember(p)">
                <VipAvatar :name="p.label" :size="30" />
                <span class="grp-result__text">
                  <span class="grp-result__label">{{ p.label }}</span>
                  <span v-if="p.detail" class="grp-result__detail">{{ p.detail }}</span>
                </span>
                <span class="grp-add-label">
                  <VipIcon name="plus" :size="15" />
                  Add
                </span>
              </button>
            </li>
          </ul>
        </section>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="membersOpen = false">Done</VipButton>
      </template>
    </VipDialog>

    <!-- Delete -->
    <VipConfirmDialog
      :open="!!deleteTarget"
      level="danger"
      title="Delete group?"
      :resource-name="deleteTarget?.name"
      message="The group will be removed and its members will lose any access granted through it."
      confirm-label="Delete group"
      :pending="deletePending"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<style scoped>
.grp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-5);
  flex-wrap: wrap;
}
.grp-toolbar > *:first-child {
  width: min(360px, 100%);
}
.grp-archived {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  cursor: pointer;
}
.grp {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.grp-name {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.grp-desc {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.grp-actions {
  display: flex;
  justify-content: flex-end;
}
.grp-menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--vip-text-secondary);
  background: none;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-md);
  cursor: pointer;
}
.grp-menu:hover {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border);
  color: var(--vip-text-primary);
}
.grp-form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.grp-members {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.grp-section {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.grp-section__title {
  margin: 0;
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.grp-section__count {
  font-weight: var(--vip-fw-regular);
  color: var(--vip-text-muted);
  text-transform: none;
  letter-spacing: 0;
}
.grp-result {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  width: 100%;
  padding: var(--vip-sp-3);
  background: none;
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  cursor: pointer;
  text-align: left;
  color: var(--vip-text-secondary);
}
.grp-result:hover {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border-strong, var(--vip-border));
}
.grp-add-label {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-1);
  font-size: var(--vip-fs-xs);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-accent, var(--vip-text-primary));
  flex: none;
}
.grp-result__text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.grp-result__label {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.grp-result__detail {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.grp-empty {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  padding: var(--vip-sp-2) 0;
}
.grp-member-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  max-height: 240px;
  overflow-y: auto;
}
.grp-member-list--available {
  max-height: 280px;
}
.grp-member {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-3);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.grp-member__text {
  flex: 1;
  min-width: 0;
}
.grp-member__name {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.grp-member__email {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
</style>
