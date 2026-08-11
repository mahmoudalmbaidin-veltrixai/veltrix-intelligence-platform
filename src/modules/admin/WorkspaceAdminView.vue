<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { adminService, type WorkspaceRow } from './admin.service'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'
import { ApiError } from '@/shared/types/api'

const platform = usePlatformStore()
const ui = useUiStore()
const tenantKey = computed(() => platform.organization?.id ?? 'none')
const {
  data,
  error: queryError,
  isLoading,
  refetch,
} = useQuery(
  () => `admin:${tenantKey.value}:workspaces`,
  () => adminService.listWorkspaces(),
)
const rows = ref<WorkspaceRow[]>([])
watch(data, (value) => (rows.value = value ?? []), { immediate: true })

const createOpen = ref(false)
const editOpen = ref(false)
const busy = ref(false)
const mutationError = ref('')
const newName = ref('')
const newSlug = ref('')
const editing = ref<WorkspaceRow | null>(null)
const editName = ref('')
const editSlug = ref('')
const deleting = ref<WorkspaceRow | null>(null)
const deleteError = ref('')

// Number of active (non-archived, non-deleted) workspaces — drives the
// last-active-workspace protection shown in the UI (backend enforces it too).
const activeCount = computed(() => rows.value.filter((row) => row.status === 'active').length)

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) {
    // Prefer the specific field-level reason (e.g. slug pattern) over the generic envelope.
    const field = cause.fieldErrors?.[0]
    if (field?.message) {
      const label = field.field?.split('.').pop()
      return label ? `${label[0].toUpperCase()}${label.slice(1)}: ${field.message}` : field.message
    }
    if (cause.message) return cause.message
  }
  return fallback
}

// Returns the reason an archive/delete is blocked, or '' when allowed.
function blockReason(workspace: WorkspaceRow, verb: 'archive' | 'delete'): string {
  if (workspace.isDefault) return 'Reassign the default workspace first'
  if (workspace.status === 'active' && activeCount.value <= 1) {
    return `You cannot ${verb} the only active workspace`
  }
  return ''
}

const columns: Column<WorkspaceRow>[] = [
  { key: 'name', label: 'Workspace' },
  { key: 'slug', label: 'Slug' },
  { key: 'status', label: 'State' },
  { key: 'isDefault', label: 'Default' },
  { key: 'actions', label: '', align: 'right' },
]

function suggestedSlug(name: string): string {
  return name
    .normalize('NFKD')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100)
}

watch(newName, (value) => {
  if (!newSlug.value || newSlug.value === suggestedSlug(newName.value.slice(0, -1))) {
    newSlug.value = suggestedSlug(value)
  }
})

// Live-sanitize slug input so spaces/capitals/invalid characters can never be
// submitted (the backend requires ^[a-z0-9]+(?:-[a-z0-9]+)*$). Kept lenient
// while typing (allows a trailing hyphen); fully normalized on submit.
function sanitizeSlugInput(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-+/, '')
}
watch(newSlug, (value) => {
  const clean = sanitizeSlugInput(value)
  if (clean !== value) newSlug.value = clean
})
watch(editSlug, (value) => {
  const clean = sanitizeSlugInput(value)
  if (clean !== value) editSlug.value = clean
})

function menuFor(workspace: WorkspaceRow) {
  const items: { key: string; label: string; icon: string; disabled?: boolean }[] = []
  if (platform.can('workspace.update')) {
    items.push({ key: 'edit', label: 'Edit', icon: 'settings' })
    if (!workspace.isDefault && workspace.status === 'active') {
      items.push({ key: 'makeDefault', label: 'Make default', icon: 'check' })
    }
  }
  if (platform.can('workspace.archive')) {
    if (workspace.status === 'archived') {
      items.push({ key: 'restore', label: 'Restore', icon: 'refresh' })
    } else {
      const reason = blockReason(workspace, 'archive')
      items.push({ key: 'archive', label: reason || 'Archive', icon: 'folder', disabled: !!reason })
    }
    const deleteReason = blockReason(workspace, 'delete')
    items.push({ key: 'delete', label: deleteReason || 'Delete', icon: 'trash', disabled: !!deleteReason })
  }
  return items
}

function openEdit(workspace: WorkspaceRow): void {
  editing.value = workspace
  editName.value = workspace.name
  editSlug.value = workspace.slug
  mutationError.value = ''
  editOpen.value = true
}

async function refreshTenantState(): Promise<void> {
  await platform.bootstrapTenancy(true)
  await refetch()
}

async function onMenu(workspace: WorkspaceRow, key: string): Promise<void> {
  if (key === 'edit') {
    openEdit(workspace)
    return
  }
  if (key === 'delete') {
    deleteError.value = ''
    deleting.value = workspace
    return
  }
  busy.value = true
  mutationError.value = ''
  try {
    if (key === 'makeDefault') {
      await adminService.setDefaultWorkspace(workspace.id)
      await refreshTenantState()
      ui.pushToast({ kind: 'success', title: 'Default workspace updated', message: workspace.name })
    } else {
      const status = key === 'archive' ? 'archived' : 'active'
      await adminService.updateWorkspace(workspace.id, { status })
      await refreshTenantState()
      ui.pushToast({
        kind: status === 'archived' ? 'warning' : 'success',
        title: status === 'archived' ? 'Workspace archived' : 'Workspace restored',
        message: workspace.name,
      })
    }
  } catch (cause) {
    mutationError.value = errorMessage(
      cause,
      'The workspace state could not be changed. Review its default status and try again.',
    )
  } finally {
    busy.value = false
  }
}

async function confirmDelete(): Promise<void> {
  const workspace = deleting.value
  if (!workspace) return
  busy.value = true
  deleteError.value = ''
  try {
    await adminService.deleteWorkspace(workspace.id)
    await refreshTenantState()
    ui.pushToast({
      kind: 'success',
      title: 'Workspace deleted',
      message: `${workspace.name} was removed. Its data is retained.`,
    })
    deleting.value = null
  } catch (cause) {
    deleteError.value = errorMessage(cause, 'The workspace could not be deleted.')
  } finally {
    busy.value = false
  }
}

async function create(): Promise<void> {
  const name = newName.value.trim()
  const slug = suggestedSlug(newSlug.value)
  if (!name || !slug) return
  busy.value = true
  mutationError.value = ''
  try {
    const created = await adminService.createWorkspace(name, slug)
    await refreshTenantState()
    await platform.switchWorkspace(created.id)
    ui.pushToast({ kind: 'success', title: 'Workspace created', message: `${created.name} is now active.` })
    createOpen.value = false
    newName.value = ''
    newSlug.value = ''
  } catch (cause) {
    mutationError.value = errorMessage(
      cause,
      'The workspace could not be created. Check the name, slug, and workspace quota.',
    )
  } finally {
    busy.value = false
  }
}

async function saveEdit(): Promise<void> {
  if (!editing.value || !editName.value.trim() || !editSlug.value.trim()) return
  busy.value = true
  mutationError.value = ''
  try {
    const updated = await adminService.updateWorkspace(editing.value.id, {
      name: editName.value.trim(),
      slug: suggestedSlug(editSlug.value),
    })
    await refreshTenantState()
    ui.pushToast({ kind: 'success', title: 'Workspace updated', message: updated.name })
    editOpen.value = false
    editing.value = null
  } catch (cause) {
    mutationError.value = errorMessage(cause, 'The workspace could not be updated. Check that the slug is unique.')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Workspace Administration"
      description="Create, edit, archive and restore persisted workspaces."
    >
      <template #actions>
        <VipButton
          v-if="platform.can('workspace.create')"
          variant="primary"
          icon="plus"
          @click="((mutationError = ''), (createOpen = true))"
          >New workspace</VipButton
        >
      </template>
    </VipPageHeader>
    <VipAlert tone="info" title="Workspace isolation">
      Every change on this page is stored by the backend and scoped to {{ platform.organization?.name }}.
    </VipAlert>
    <VipAlert v-if="mutationError" tone="danger" title="Workspace operation failed">{{ mutationError }}</VipAlert>
    <VipAlert v-if="queryError" tone="danger" title="Workspaces unavailable">
      The persisted workspace list could not be loaded.
    </VipAlert>

    <VipTable :columns="columns" :rows="rows" :row-key="(row) => row.id" :loading="isLoading" style="margin-top: 16px">
      <template #cell-status="{ row }">
        <VipBadge :tone="row.status === 'active' ? 'success' : 'neutral'" size="sm">{{ row.status }}</VipBadge>
      </template>
      <template #cell-isDefault="{ row }">
        <VipBadge :tone="row.isDefault ? 'brand' : 'neutral'" size="sm">{{ row.isDefault ? 'default' : '—' }}</VipBadge>
      </template>
      <template #cell-actions="{ row }">
        <VipMenu v-if="menuFor(row).length" :items="menuFor(row)" @select="onMenu(row, $event)">
          <template #trigger>
            <VipButton
              variant="ghost"
              size="xs"
              icon="dotsV"
              :disabled="busy"
              :aria-label="`Actions for ${row.name}`"
            />
          </template>
        </VipMenu>
      </template>
    </VipTable>

    <VipDialog :open="createOpen" title="Create workspace" size="sm" @close="createOpen = false">
      <VipInput v-model="newName" label="Workspace name" placeholder="Marketing Analytics" required />
      <div style="margin-top: 12px">
        <VipInput v-model="newSlug" label="Workspace slug" placeholder="marketing-analytics" required />
      </div>
      <VipAlert v-if="mutationError" tone="danger" title="Creation failed">{{ mutationError }}</VipAlert>
      <template #footer>
        <VipButton variant="tertiary" :disabled="busy" @click="createOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="busy" :disabled="!newName.trim() || !newSlug.trim()" @click="create">
          Create workspace
        </VipButton>
      </template>
    </VipDialog>

    <VipDialog :open="editOpen" title="Edit workspace" size="sm" @close="editOpen = false">
      <VipInput v-model="editName" label="Workspace name" required />
      <div style="margin-top: 12px"><VipInput v-model="editSlug" label="Workspace slug" required /></div>
      <VipAlert v-if="mutationError" tone="danger" title="Update failed">{{ mutationError }}</VipAlert>
      <template #footer>
        <VipButton variant="tertiary" :disabled="busy" @click="editOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="busy" :disabled="!editName.trim() || !editSlug.trim()" @click="saveEdit">
          Save changes
        </VipButton>
      </template>
    </VipDialog>

    <VipConfirmDialog
      :open="deleting !== null"
      level="danger"
      title="Delete workspace?"
      :resource-name="deleting?.name"
      message="The workspace will be removed from navigation and management. Its datasets, pipelines, dashboards and audit history are retained — nothing is cascade-deleted."
      confirm-label="Delete workspace"
      :pending="busy"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="deleting = null"
    />
  </div>
</template>
