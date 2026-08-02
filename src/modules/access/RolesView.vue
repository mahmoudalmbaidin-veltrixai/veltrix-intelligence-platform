<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import {
  accessService,
  type PermissionCatalogItem,
  type Principal,
  type Role,
  type RoleAssignment,
} from './access.service'
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

const canCreate = computed(() => platform.can('role.create'))
const canUpdate = computed(() => platform.can('role.update'))
const canDelete = computed(() => platform.can('role.delete'))
const canAssign = computed(() => platform.can('role.assign'))

const includeArchived = ref(false)
const {
  data,
  error: queryError,
  isLoading,
  refetch,
} = useQuery(
  () => `access:${tenantKey.value}:roles:${includeArchived.value}`,
  () => accessService.listRoles({ includeArchived: includeArchived.value }),
)
const roles = ref<Role[]>([])
watch(data, (d) => (roles.value = d ?? []), { immediate: true })

const catalog = ref<PermissionCatalogItem[]>([])
const catalogError = ref<string | null>(null)
async function ensureCatalog() {
  if (catalog.value.length) return
  try {
    catalog.value = await accessService.permissionCatalog()
  } catch (e) {
    catalogError.value = safeErrorText(e)
  }
}

const search = ref('')
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return roles.value
  return roles.value.filter((r) => r.name.toLowerCase().includes(q))
})

const columns = computed<Column<Role>[]>(() => [
  { key: 'name', label: 'Role' },
  { key: 'scope', label: 'Scope' },
  { key: 'permission_keys', label: 'Permissions' },
  { key: 'assignment_count', label: 'Assignments' },
  { key: 'status', label: 'Status' },
  { key: 'actions', label: '', align: 'right' as const },
])

function titleCase(value: string): string {
  return value.replace(/(^|[._])([a-z])/g, (_m, p, c: string) => (p ? ' ' : '') + c.toUpperCase())
}

// --- editor (create / edit) ---
const editOpen = ref(false)
const editTarget = ref<Role | null>(null)
const formName = ref('')
const formDescription = ref('')
const formScope = ref('organization')
const selectedKeys = ref<Set<string>>(new Set())
const permSearch = ref('')
const formSubmitting = ref(false)
const formError = ref<string | null>(null)
const formValid = computed(() => formName.value.trim().length >= 2)

const visibleCatalog = computed(() =>
  catalog.value.filter((p) => (formScope.value === 'workspace' ? p.scope === 'workspace' : true)),
)
const categories = computed(() => {
  const q = permSearch.value.trim().toLowerCase()
  const groups = new Map<string, PermissionCatalogItem[]>()
  for (const item of visibleCatalog.value) {
    if (q && !item.key.toLowerCase().includes(q) && !item.name.toLowerCase().includes(q)) continue
    const list = groups.get(item.category) ?? []
    list.push(item)
    groups.set(item.category, list)
  }
  return [...groups.entries()]
    .map(([category, items]) => ({ category, items }))
    .sort((a, b) => a.category.localeCompare(b.category))
})

async function openCreate() {
  editTarget.value = null
  formName.value = ''
  formDescription.value = ''
  formScope.value = 'organization'
  selectedKeys.value = new Set()
  permSearch.value = ''
  formError.value = null
  catalogError.value = null
  // Open first so a catalog fetch failure cannot leave the button looking dead.
  editOpen.value = true
  await ensureCatalog()
}
async function openEdit(role: Role) {
  editTarget.value = role
  formName.value = role.name
  formDescription.value = role.description
  formScope.value = role.scope
  selectedKeys.value = new Set(role.permission_keys)
  permSearch.value = ''
  formError.value = null
  editOpen.value = true
  await ensureCatalog()
}
function isSelected(key: string): boolean {
  return selectedKeys.value.has(key)
}
function toggleKey(key: string) {
  const next = new Set(selectedKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  selectedKeys.value = next
}
function selectCategory(items: PermissionCatalogItem[], on: boolean) {
  const next = new Set(selectedKeys.value)
  for (const item of items) {
    if (on) next.add(item.key)
    else next.delete(item.key)
  }
  selectedKeys.value = next
}
function categoryState(items: PermissionCatalogItem[]): 'all' | 'some' | 'none' {
  const count = items.filter((i) => selectedKeys.value.has(i.key)).length
  if (count === 0) return 'none'
  return count === items.length ? 'all' : 'some'
}

async function submitForm() {
  if (!formValid.value || formSubmitting.value) return
  formSubmitting.value = true
  formError.value = null
  const keys = [...selectedKeys.value]
  try {
    if (editTarget.value) {
      await accessService.updateRole(editTarget.value.id, editTarget.value.row_version, {
        name: formName.value.trim(),
        description: formDescription.value.trim(),
        permission_keys: keys,
      })
      ui.pushToast({ kind: 'success', title: 'Role updated', message: formName.value.trim() })
    } else {
      await accessService.createRole({
        name: formName.value.trim(),
        description: formDescription.value.trim(),
        scope: formScope.value as 'organization' | 'workspace',
        permission_keys: keys,
      })
      ui.pushToast({ kind: 'success', title: 'Role created', message: formName.value.trim() })
    }
    editOpen.value = false
    await refetch()
  } catch (e) {
    formError.value = safeErrorText(e)
  } finally {
    formSubmitting.value = false
  }
}

// --- clone ---
const cloneTarget = ref<Role | null>(null)
const cloneName = ref('')
const clonePending = ref(false)
const cloneError = ref<string | null>(null)
function openClone(role: Role) {
  cloneTarget.value = role
  cloneName.value = `${role.name} (copy)`
  cloneError.value = null
}
async function confirmClone() {
  if (!cloneTarget.value || clonePending.value) return
  clonePending.value = true
  cloneError.value = null
  try {
    await accessService.cloneRole(cloneTarget.value.id, cloneName.value.trim())
    ui.pushToast({ kind: 'success', title: 'Role cloned', message: cloneName.value.trim() })
    cloneTarget.value = null
    await refetch()
  } catch (e) {
    cloneError.value = safeErrorText(e)
  } finally {
    clonePending.value = false
  }
}

async function toggleArchive(role: Role) {
  try {
    await accessService.archiveRole(role.id, role.row_version, !role.archived_at)
    ui.pushToast({
      kind: 'success',
      title: role.archived_at ? 'Role restored' : 'Role archived',
      message: role.name,
    })
    await refetch()
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Action failed', message: safeErrorText(e) })
  }
}

// --- delete ---
const deleteTarget = ref<Role | null>(null)
const deletePending = ref(false)
const deleteError = ref<string | null>(null)
async function confirmDelete() {
  if (!deleteTarget.value) return
  deletePending.value = true
  deleteError.value = null
  try {
    await accessService.deleteRole(deleteTarget.value.id, deleteTarget.value.row_version)
    ui.pushToast({ kind: 'success', title: 'Role deleted', message: deleteTarget.value.name })
    deleteTarget.value = null
    await refetch()
  } catch (e) {
    deleteError.value = safeErrorText(e)
  } finally {
    deletePending.value = false
  }
}

// --- assignments ---
const assignOpen = ref(false)
const assignRole = ref<Role | null>(null)
const assignments = ref<RoleAssignment[]>([])
const assignLoading = ref(false)
const assignError = ref<string | null>(null)
const subjectQuery = ref('')
const subjectResults = ref<Principal[]>([])
const subjectSearching = ref(false)
let subjectTimer: ReturnType<typeof setTimeout> | null = null

async function openAssignments(role: Role) {
  assignRole.value = role
  assignOpen.value = true
  subjectQuery.value = ''
  subjectResults.value = []
  await loadAssignments()
}
async function loadAssignments() {
  if (!assignRole.value) return
  assignLoading.value = true
  assignError.value = null
  try {
    assignments.value = await accessService.listRoleAssignments(assignRole.value.id)
  } catch (e) {
    assignError.value = safeErrorText(e)
  } finally {
    assignLoading.value = false
  }
}
watch(subjectQuery, (value) => {
  if (subjectTimer) clearTimeout(subjectTimer)
  const q = value.trim()
  if (q.length < 2) {
    subjectResults.value = []
    return
  }
  subjectTimer = setTimeout(async () => {
    subjectSearching.value = true
    try {
      subjectResults.value = await accessService.searchPrincipals(q)
    } catch {
      subjectResults.value = []
    } finally {
      subjectSearching.value = false
    }
  }, 250)
})
async function addAssignment(principal: Principal) {
  if (!assignRole.value) return
  try {
    await accessService.assignRole(assignRole.value.id, principal.principal_type, principal.id)
    ui.pushToast({ kind: 'success', title: 'Role assigned', message: principal.label })
    subjectQuery.value = ''
    subjectResults.value = []
    await Promise.all([loadAssignments(), refetch()])
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Could not assign', message: safeErrorText(e) })
  }
}
async function removeAssignment(item: RoleAssignment) {
  if (!assignRole.value) return
  try {
    await accessService.unassignRole(assignRole.value.id, item.id, item.subject_type)
    ui.pushToast({ kind: 'success', title: 'Assignment removed', message: item.subject_label })
    await Promise.all([loadAssignments(), refetch()])
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Could not remove', message: safeErrorText(e) })
  }
}

function rowMenu(role: Role) {
  const items: { key: string; label: string; icon?: string; danger?: boolean }[] = []
  if (canAssign.value) items.push({ key: 'assign', label: 'Assignments', icon: 'users' })
  if (!role.is_system && canUpdate.value) {
    items.push({ key: 'edit', label: 'Edit', icon: 'text' })
    items.push({
      key: 'archive',
      label: role.archived_at ? 'Restore' : 'Archive',
      icon: role.archived_at ? 'refresh' : 'folder',
    })
  }
  if (canCreate.value) items.push({ key: 'clone', label: 'Clone', icon: 'copy' })
  if (!role.is_system && canDelete.value) {
    items.push({ key: 'delete', label: 'Delete', icon: 'trash', danger: true })
  }
  return items
}
function onRowAction(role: Role, key: string) {
  if (key === 'assign') void openAssignments(role)
  else if (key === 'edit') void openEdit(role)
  else if (key === 'archive') void toggleArchive(role)
  else if (key === 'clone') openClone(role)
  else if (key === 'delete') {
    deleteError.value = null
    deleteTarget.value = role
  }
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Roles"
      description="System and custom roles. Custom roles bundle permissions from the authoritative catalog and can be assigned to users and groups."
    >
      <template #actions>
        <VipButton v-if="canCreate" variant="primary" icon="plus" @click="openCreate">New role</VipButton>
      </template>
    </VipPageHeader>

    <VipAlert v-if="queryError" tone="danger" title="Roles unavailable">
      The role list could not be loaded. Check your connection and permissions, then retry.
    </VipAlert>

    <div class="rl-toolbar">
      <VipInput v-model="search" icon="search" size="sm" placeholder="Search roles" />
      <label class="rl-archived">
        <input v-model="includeArchived" type="checkbox" />
        Show archived
      </label>
    </div>

    <VipTable
      :columns="columns"
      :rows="filtered"
      :row-key="(r) => r.id"
      :loading="isLoading"
      empty-title="No roles yet"
      empty-description="Create a custom role to bundle permissions for a team."
    >
      <template #cell-name="{ row }">
        <div class="rl-name">
          <div class="rl-name__title">{{ row.name }}</div>
          <div v-if="row.description" class="rl-name__desc">{{ row.description }}</div>
        </div>
      </template>
      <template #cell-scope="{ row }">
        <VipBadge tone="neutral" size="sm">{{ row.scope }}</VipBadge>
      </template>
      <template #cell-permission_keys="{ row }">
        <VipBadge tone="info" size="sm">{{ (row.permission_keys ?? []).length }}</VipBadge>
      </template>
      <template #cell-assignment_count="{ row }">
        <VipBadge tone="neutral" size="sm">{{ row.assignment_count ?? 0 }}</VipBadge>
      </template>
      <template #cell-status="{ row }">
        <div class="rl-status">
          <VipBadge v-if="row.is_system" tone="info" size="sm">system</VipBadge>
          <VipBadge v-else :tone="row.archived_at ? 'warning' : 'success'" size="sm">
            {{ row.archived_at ? 'archived' : 'custom' }}
          </VipBadge>
        </div>
      </template>
      <template #cell-actions="{ row }">
        <div class="rl-actions">
          <VipMenu :items="rowMenu(row)" align="end" @select="(k) => onRowAction(row, k)">
            <template #trigger>
              <button class="rl-menu" :aria-label="`Actions for ${row.name}`">
                <VipIcon name="dotsV" :size="16" />
              </button>
            </template>
          </VipMenu>
        </div>
      </template>
    </VipTable>

    <!-- editor -->
    <VipDialog
      :open="editOpen"
      :title="editTarget ? `Edit role · ${editTarget.name}` : 'New custom role'"
      size="lg"
      :closable="!formSubmitting"
      @close="editOpen = false"
    >
      <div class="rl-form">
        <div class="rl-form__row">
          <VipInput v-model="formName" label="Role name" placeholder="e.g. Report Curator" required />
          <VipSelect
            v-model="formScope"
            label="Scope"
            :disabled="!!editTarget"
            :options="[
              { value: 'organization', label: 'Organization' },
              { value: 'workspace', label: 'Workspace' },
            ]"
          />
        </div>
        <VipInput v-model="formDescription" label="Description" placeholder="Optional summary" />

        <div class="rl-matrix">
          <div class="rl-matrix__head">
            <h3 class="rl-h">
              Permissions <span class="rl-count">({{ selectedKeys.size }} selected)</span>
            </h3>
            <VipInput v-model="permSearch" icon="search" size="sm" placeholder="Filter permissions" />
          </div>
          <VipAlert v-if="catalogError" tone="danger" title="Catalog unavailable">{{ catalogError }}</VipAlert>
          <div v-for="group in categories" :key="group.category" class="rl-cat">
            <div class="rl-cat__head">
              <span class="rl-cat__name">{{ titleCase(group.category) }}</span>
              <span class="rl-cat__actions">
                <button
                  type="button"
                  class="rl-link"
                  :disabled="categoryState(group.items) === 'all'"
                  @click="selectCategory(group.items, true)"
                >
                  Select all
                </button>
                <button
                  type="button"
                  class="rl-link"
                  :disabled="categoryState(group.items) === 'none'"
                  @click="selectCategory(group.items, false)"
                >
                  Clear
                </button>
              </span>
            </div>
            <ul class="rl-perms">
              <li v-for="perm in group.items" :key="perm.key" class="rl-perm">
                <label class="rl-perm__label" :title="perm.description || perm.key">
                  <input type="checkbox" :checked="isSelected(perm.key)" @change="toggleKey(perm.key)" />
                  <span class="rl-perm__text">
                    <span class="rl-perm__name">{{ perm.name }}</span>
                    <span class="rl-perm__key">{{ perm.key }}</span>
                  </span>
                </label>
              </li>
            </ul>
          </div>
        </div>

        <VipAlert v-if="formError" tone="danger" title="Could not save">{{ formError }}</VipAlert>
      </div>
      <template #footer>
        <VipButton variant="tertiary" :disabled="formSubmitting" @click="editOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="formSubmitting" :disabled="!formValid" @click="submitForm">
          {{ editTarget ? 'Save changes' : 'Create role' }}
        </VipButton>
      </template>
    </VipDialog>

    <!-- clone -->
    <VipDialog :open="!!cloneTarget" title="Clone role" size="sm" :closable="!clonePending" @close="cloneTarget = null">
      <div class="rl-form">
        <p class="rl-hint">Creates a new editable custom role with the same permissions.</p>
        <VipInput v-model="cloneName" label="New role name" required @enter="confirmClone" />
        <VipAlert v-if="cloneError" tone="danger" title="Could not clone">{{ cloneError }}</VipAlert>
      </div>
      <template #footer>
        <VipButton variant="tertiary" :disabled="clonePending" @click="cloneTarget = null">Cancel</VipButton>
        <VipButton variant="primary" :loading="clonePending" @click="confirmClone">Clone role</VipButton>
      </template>
    </VipDialog>

    <!-- assignments -->
    <VipDialog
      :open="assignOpen"
      :title="assignRole ? `Assignments · ${assignRole.name}` : 'Assignments'"
      size="md"
      @close="assignOpen = false"
    >
      <div class="rl-assign">
        <div v-if="canAssign" class="rl-search">
          <VipInput v-model="subjectQuery" icon="search" placeholder="Search users and groups" autocomplete="off" />
          <ul v-if="subjectResults.length" class="rl-results">
            <li v-for="p in subjectResults" :key="`${p.principal_type}:${p.id}`">
              <button type="button" class="rl-result" @click="addAssignment(p)">
                <VipAvatar :name="p.label" :size="26" />
                <span class="rl-result__text">
                  <span class="rl-result__label">{{ p.label }}</span>
                  <span v-if="p.detail" class="rl-result__detail">{{ p.detail }}</span>
                </span>
                <VipBadge size="sm" :tone="p.principal_type === 'group' ? 'info' : 'neutral'">
                  {{ p.principal_type }}
                </VipBadge>
              </button>
            </li>
          </ul>
          <p v-else-if="subjectQuery.trim().length >= 2 && !subjectSearching" class="rl-empty">No matches found.</p>
        </div>

        <VipAlert v-if="assignError" tone="danger" title="Could not load assignments">{{ assignError }}</VipAlert>
        <p v-if="assignLoading" class="rl-empty">Loading…</p>
        <p v-else-if="!assignments.length" class="rl-empty">No assignments yet.</p>
        <ul v-else class="rl-assign-list">
          <li v-for="item in assignments" :key="item.id" class="rl-assign-item">
            <VipAvatar :name="item.subject_label" :size="30" />
            <div class="rl-assign-item__text">
              <div class="rl-assign-item__label">
                {{ item.subject_label }}
                <VipBadge v-if="item.subject_type === 'group'" size="sm" tone="info">group</VipBadge>
              </div>
              <div class="rl-assign-item__meta">{{ item.scope }} · {{ formatDateTime(item.created_at) }}</div>
            </div>
            <button
              v-if="canAssign"
              class="rl-menu"
              :aria-label="`Remove ${item.subject_label}`"
              @click="removeAssignment(item)"
            >
              <VipIcon name="close" :size="15" />
            </button>
          </li>
        </ul>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="assignOpen = false">Done</VipButton>
      </template>
    </VipDialog>

    <VipConfirmDialog
      :open="!!deleteTarget"
      level="danger"
      title="Delete role?"
      :resource-name="deleteTarget?.name"
      message="The role and all of its assignments will be removed. Users keep access from other roles."
      confirm-label="Delete role"
      :pending="deletePending"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<style scoped>
.rl-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  margin-bottom: var(--vip-sp-5);
  flex-wrap: wrap;
}
.rl-toolbar > *:first-child {
  width: min(360px, 100%);
}
.rl-archived {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  cursor: pointer;
}
.rl-name__title {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.rl-name__desc {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.rl-status,
.rl-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--vip-sp-2);
}
.rl-menu {
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
.rl-menu:hover {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border);
  color: var(--vip-text-primary);
}
.rl-form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.rl-form__row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--vip-sp-4);
}
.rl-hint {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.rl-matrix {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.rl-matrix__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-3);
}
.rl-matrix__head > *:last-child {
  width: min(260px, 100%);
}
.rl-h {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.rl-count {
  color: var(--vip-text-muted);
  font-weight: var(--vip-fw-regular);
  text-transform: none;
}
.rl-cat {
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  overflow: hidden;
}
.rl-cat__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--vip-sp-2) var(--vip-sp-3);
  background: var(--vip-surface-subtle);
  border-bottom: 1px solid var(--vip-border);
}
.rl-cat__name {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.rl-cat__actions {
  display: flex;
  gap: var(--vip-sp-3);
}
.rl-link {
  background: none;
  border: none;
  color: var(--vip-accent-text, var(--vip-text-secondary));
  font-size: var(--vip-fs-xs);
  cursor: pointer;
}
.rl-link:disabled {
  color: var(--vip-text-disabled, var(--vip-text-muted));
  cursor: default;
}
.rl-perms {
  list-style: none;
  margin: 0;
  padding: var(--vip-sp-2);
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--vip-sp-1);
}
.rl-perm__label {
  display: flex;
  align-items: flex-start;
  gap: var(--vip-sp-2);
  padding: var(--vip-sp-2);
  border-radius: var(--vip-radius-sm);
  cursor: pointer;
}
.rl-perm__label:hover {
  background: var(--vip-surface-hover);
}
.rl-perm__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.rl-perm__name {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
}
.rl-perm__key {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  font-family: var(--vip-font-mono, monospace);
}
.rl-assign,
.rl-assign-list {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.rl-assign {
  gap: var(--vip-sp-4);
}
.rl-search {
  position: relative;
}
.rl-results {
  list-style: none;
  margin: var(--vip-sp-2) 0 0;
  padding: var(--vip-sp-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface);
  box-shadow: var(--vip-shadow-md);
  max-height: 220px;
  overflow-y: auto;
}
.rl-result {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  width: 100%;
  padding: var(--vip-sp-2) var(--vip-sp-3);
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  cursor: pointer;
  text-align: left;
}
.rl-result:hover {
  background: var(--vip-surface-hover);
}
.rl-result__text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.rl-result__label {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.rl-result__detail {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.rl-empty {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  padding: var(--vip-sp-2) 0;
}
.rl-assign-item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-3);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.rl-assign-item__text {
  flex: 1;
  min-width: 0;
}
.rl-assign-item__label {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.rl-assign-item__meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
@media (max-width: 640px) {
  .rl-form__row,
  .rl-perms {
    grid-template-columns: 1fr;
  }
}
</style>
