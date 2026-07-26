<script setup lang="ts">
import { ref, watch } from 'vue'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { governanceService, type RoleDto } from '@/shared/services/governance/apiGovernanceService'
import { adminService } from './admin.service'
import MembersView from './MembersView.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const tab = ref('profile')
const tabs = [
  { value: 'profile', label: 'Profile' },
  { value: 'members', label: 'Members' },
  { value: 'roles', label: 'Roles' },
]
const orgName = ref('')
const orgSlug = ref('')
const roles = ref<RoleDto[]>([])
const saving = ref(false)
const saveError = ref('')

watch(
  () => platform.organization,
  async (organization) => {
    orgName.value = organization?.name ?? ''
    orgSlug.value = organization?.slug ?? ''
    roles.value = []
    if (organization && platform.can('governance.read')) roles.value = await governanceService.roles()
  },
  { immediate: true },
)

async function save(): Promise<void> {
  if (!orgName.value.trim() || !orgSlug.value.trim()) return
  saving.value = true
  saveError.value = ''
  try {
    await adminService.updateOrganization(orgName.value.trim(), orgSlug.value.trim())
    await platform.bootstrapTenancy(true)
    ui.pushToast({ kind: 'success', title: 'Organization updated', message: orgName.value.trim() })
  } catch {
    saveError.value = 'The organization could not be updated. Check that the slug is valid and unique.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Organization Administration"
      :description="platform.organization?.name ?? 'No organization selected'"
    />
    <VipTabs v-model="tab" :tabs="tabs" />
    <div class="oa">
      <template v-if="tab === 'profile'">
        <VipCard class="oa-form">
          <VipAlert tone="info" title="Persisted organization profile">
            Changes are validated and stored by the tenant API.
          </VipAlert>
          <VipAlert v-if="saveError" tone="danger" title="Update failed">{{ saveError }}</VipAlert>
          <VipInput v-model="orgName" label="Organization name" required />
          <VipInput v-model="orgSlug" label="Organization slug" required />
          <VipInput :model-value="platform.user.name" label="Signed-in user" readonly />
          <VipButton
            v-if="platform.can('organization.update')"
            variant="primary"
            :loading="saving"
            :disabled="!orgName.trim() || !orgSlug.trim()"
            @click="save"
            >Save changes</VipButton
          >
        </VipCard>
      </template>
      <MembersView v-else-if="tab === 'members'" />
      <template v-else>
        <div class="oa-roles">
          <VipCard v-for="role in roles" :key="role.key">
            <div class="oa-role-head">
              <strong>{{ role.name }}</strong>
              <VipBadge tone="neutral" size="sm">{{ role.permissions.length }} permissions</VipBadge>
            </div>
            <p class="oa-role-desc">
              {{ role.scope }} scope · {{ role.is_assignable ? 'assignable' : 'system managed' }}
            </p>
          </VipCard>
          <VipAlert v-if="roles.length === 0" tone="info" title="Roles unavailable">
            The active role cannot view the governance catalog.
          </VipAlert>
        </div>
      </template>
    </div>
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
</style>
