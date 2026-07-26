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

function menuFor(workspace: WorkspaceRow) {
  const items = []
  if (platform.can('workspace.update')) items.push({ key: 'edit', label: 'Edit', icon: 'settings' })
  if (platform.can('workspace.archive')) {
    items.push(
      workspace.status === 'archived'
        ? { key: 'restore', label: 'Restore', icon: 'refresh' }
        : {
            key: 'archive',
            label: workspace.isDefault ? 'Default workspace cannot be archived' : 'Archive',
            icon: 'folder',
            disabled: workspace.isDefault,
          },
    )
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
  busy.value = true
  mutationError.value = ''
  try {
    const status = key === 'archive' ? 'archived' : 'active'
    await adminService.updateWorkspace(workspace.id, { status })
    await refreshTenantState()
    ui.pushToast({
      kind: status === 'archived' ? 'warning' : 'success',
      title: status === 'archived' ? 'Workspace archived' : 'Workspace restored',
      message: workspace.name,
    })
  } catch {
    mutationError.value = 'The workspace state could not be changed. Review its default status and try again.'
  } finally {
    busy.value = false
  }
}

async function create(): Promise<void> {
  const name = newName.value.trim()
  const slug = newSlug.value.trim()
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
  } catch {
    mutationError.value = 'The workspace could not be created. Check the name, slug, and workspace quota.'
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
      slug: editSlug.value.trim(),
    })
    await refreshTenantState()
    ui.pushToast({ kind: 'success', title: 'Workspace updated', message: updated.name })
    editOpen.value = false
    editing.value = null
  } catch {
    mutationError.value = 'The workspace could not be updated. Check that the slug is unique.'
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
  </div>
</template>
