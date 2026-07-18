<script setup lang="ts">
import { ref, watch } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { adminService, type WorkspaceRow } from './admin.service'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const { data } = useQuery('admin:workspaces', () => adminService.listWorkspaces())
const rows = ref<WorkspaceRow[]>([])
watch(
  data,
  (d) => {
    if (d) rows.value = d
  },
  { immediate: true },
)

const createOpen = ref(false)
const newName = ref('')

const columns: Column<WorkspaceRow>[] = [
  { key: 'name', label: 'Workspace' },
  { key: 'members', label: 'Members', align: 'right' },
  { key: 'archived', label: 'State' },
  { key: 'createdAt', label: 'Created' },
  { key: 'actions', label: '', align: 'right' },
]
function menuFor(w: WorkspaceRow) {
  return [
    { key: 'edit', label: 'Edit', icon: 'settings' },
    w.archived
      ? { key: 'restore', label: 'Restore', icon: 'refresh' }
      : { key: 'archive', label: 'Archive', icon: 'folder' },
    { key: 'delete', label: 'Delete', icon: 'trash', danger: true },
  ]
}
function onMenu(w: WorkspaceRow, key: string) {
  if (key === 'archive') {
    w.archived = true
    ui.pushToast({ kind: 'warning', title: 'Workspace archived', message: w.name })
  } else if (key === 'restore') {
    w.archived = false
    ui.pushToast({ kind: 'success', title: 'Workspace restored', message: w.name })
  } else ui.pushToast({ kind: 'info', title: key, message: `${w.name} — dependency checks run before ${key}.` })
}
function create() {
  rows.value.unshift({
    id: `ws_${Date.now()}`,
    name: newName.value,
    members: 1,
    archived: false,
    createdAt: new Date().toISOString(),
  })
  ui.pushToast({ kind: 'success', title: 'Workspace created', message: newName.value })
  createOpen.value = false
  newName.value = ''
}
</script>

<template>
  <div>
    <VipPageHeader title="Workspace Administration" description="Create, edit, archive and govern workspaces.">
      <template #actions
        ><VipButton variant="primary" icon="plus" @click="createOpen = true">New workspace</VipButton></template
      >
    </VipPageHeader>
    <VipAlert tone="info" title="Workspace isolation"
      >Resources and permissions are isolated per workspace. Archiving hides a workspace without deleting its
      data.</VipAlert
    >
    <VipTable :columns="columns" :rows="rows" :row-key="(r) => r.id" style="margin-top: 16px">
      <template #cell-archived="{ row }"
        ><VipBadge :tone="row.archived ? 'neutral' : 'success'" size="sm">{{
          row.archived ? 'archived' : 'active'
        }}</VipBadge></template
      >
      <template #cell-createdAt="{ row }">{{ relativeTime(row.createdAt) }}</template>
      <template #cell-actions="{ row }">
        <VipMenu :items="menuFor(row)" @select="onMenu(row, $event)">
          <template #trigger><VipButton variant="ghost" size="xs" icon="dotsV" /></template>
        </VipMenu>
      </template>
    </VipTable>

    <VipDialog :open="createOpen" title="Create workspace" size="sm" @close="createOpen = false">
      <VipInput v-model="newName" label="Workspace name" placeholder="Marketing Analytics" required />
      <template #footer>
        <VipButton variant="tertiary" @click="createOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :disabled="!newName" @click="create">Create</VipButton>
      </template>
    </VipDialog>
  </div>
</template>
