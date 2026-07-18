<script setup lang="ts">
import { ref } from 'vue'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { ROLES } from '@/shared/permissions/roles'
import type { RoleKey } from '@/shared/types/identity'
import MembersView from './MembersView.vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const tab = ref('profile')
const tabs = [
  { value: 'profile', label: 'Profile' },
  { value: 'members', label: 'Members' },
  { value: 'roles', label: 'Roles' },
  { value: 'domains', label: 'Domains' },
  { value: 'retention', label: 'Retention' },
  { value: 'danger', label: 'Danger zone' },
]
const orgName = ref(platform.organization.name)
const legalName = ref('Veltrix Global FZ-LLC')
const domains = ref(['veltrix.com', 'shabakkatksa.com'])
const newDomain = ref('')
const deleteOpen = ref(false)

function save() {
  ui.pushToast({ kind: 'success', title: 'Organization updated' })
}
function addDomain() {
  if (newDomain.value) {
    domains.value.push(newDomain.value)
    newDomain.value = ''
  }
}
</script>

<template>
  <div>
    <VipPageHeader title="Organization Administration" :description="platform.organization.name" />
    <VipTabs v-model="tab" :tabs="tabs" />
    <div class="oa">
      <template v-if="tab === 'profile'">
        <VipCard class="oa-form">
          <VipInput v-model="orgName" label="Organization name" />
          <VipInput v-model="legalName" label="Legal / business name" />
          <VipInput :model-value="platform.user.name" label="Owner" readonly />
          <VipButton variant="primary" @click="save">Save changes</VipButton>
        </VipCard>
      </template>
      <MembersView v-else-if="tab === 'members'" />
      <template v-else-if="tab === 'roles'">
        <div class="oa-roles">
          <VipCard v-for="key in Object.keys(ROLES) as RoleKey[]" :key="key">
            <div class="oa-role-head">
              <strong>{{ ROLES[key].label }}</strong
              ><VipBadge tone="neutral" size="sm">{{
                (ROLES[key].permissions as string[]).includes('*')
                  ? 'full access'
                  : `${(ROLES[key].permissions as string[]).length} permissions`
              }}</VipBadge>
            </div>
            <p class="oa-role-desc">{{ ROLES[key].description }}</p>
          </VipCard>
        </div>
      </template>
      <template v-else-if="tab === 'domains'">
        <VipCard class="oa-form">
          <div class="oa-domains">
            <VipBadge v-for="d in domains" :key="d" tone="brand">{{ d }}</VipBadge>
          </div>
          <div class="oa-add">
            <VipInput v-model="newDomain" placeholder="add-domain.com" /><VipButton
              variant="secondary"
              icon="plus"
              @click="addDomain"
              >Add</VipButton
            >
          </div>
          <p class="oa-hint">Members must use an email from an approved domain.</p>
        </VipCard>
      </template>
      <template v-else-if="tab === 'retention'">
        <VipCard class="oa-form">
          <VipInput model-value="365 days" label="Audit & run history retention" />
          <VipInput model-value="30 days" label="Deleted-resource recovery window" />
          <VipButton variant="primary" @click="save">Save</VipButton>
        </VipCard>
      </template>
      <template v-else>
        <VipAlert tone="danger" title="Danger zone"
          >These actions are irreversible and require backend confirmation.</VipAlert
        >
        <div class="oa-danger">
          <VipButton
            variant="secondary"
            icon="share"
            @click="
              ui.pushToast({ kind: 'info', title: 'Transfer ownership', message: 'Requires owner re-authentication.' })
            "
            >Transfer ownership</VipButton
          >
          <VipButton variant="danger" icon="trash" @click="deleteOpen = true">Delete organization</VipButton>
        </div>
      </template>
    </div>

    <VipDialog
      :open="deleteOpen"
      title="Delete organization"
      description="This schedules the organization for deletion."
      size="sm"
      @close="deleteOpen = false"
    >
      <VipAlert tone="danger" title="This cannot be undone"
        >All workspaces, datasets, dashboards and members will be permanently removed after the recovery
        window.</VipAlert
      >
      <template #footer>
        <VipButton variant="tertiary" @click="deleteOpen = false">Cancel</VipButton>
        <VipButton
          variant="danger"
          @click="((deleteOpen = false), ui.pushToast({ kind: 'warning', title: 'Deletion scheduled' }))"
          >Schedule deletion</VipButton
        >
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.oa {
  margin-top: var(--vip-sp-7);
}
.oa-form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
  max-width: 560px;
}
.oa-roles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--vip-sp-5);
}
.oa-role-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.oa-role-desc {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-3);
}
.oa-domains {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3);
}
.oa-add {
  display: flex;
  gap: var(--vip-sp-3);
  align-items: flex-end;
}
.oa-add > :first-child {
  flex: 1;
}
.oa-hint {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.oa-danger {
  display: flex;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-6);
}
</style>
