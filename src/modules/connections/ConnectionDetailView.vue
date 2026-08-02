<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, invalidateQueries } from '@/shared/lib/query'
import { usePlatformStore } from '@/shared/stores/platform'
import { mapResourceAccess, resourceCan } from '@/shared/lib/resourceAccess'
import { useUiStore } from '@/shared/stores/ui'
import { formatDateTime, formatDuration } from '@/shared/lib/format'
import { connectionService, type ConnectionHealth, type ConnectionTestResult } from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import ResourceShareButton from '@/modules/access/ResourceShareButton.vue'

const route = useRoute()
const router = useRouter()
const platform = usePlatformStore()
const ui = useUiStore()
const id = computed(() => String(route.params.id))
const hasValidId = computed(() =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id.value),
)
const {
  data: connection,
  isLoading,
  refetch,
} = useQuery(
  () => `connections:detail:${id.value}`,
  () => connectionService.get(id.value),
  { enabled: hasValidId },
)
// Resource-aware capabilities from the backend effective-access decision (the
// authoritative source). Fall back to broad workspace permissions only until the
// detail response has loaded. Backend still enforces every action independently.
const access = computed(() => mapResourceAccess(connection.value?.access))
const canEdit = computed(() => (access.value ? resourceCan(access.value, 'edit') : platform.can('connection.update')))
const canTest = computed(() => (access.value ? resourceCan(access.value, 'test') : platform.can('connection.test')))
const canRotate = computed(() =>
  access.value ? resourceCan(access.value, 'rotate') : platform.can('connection.credentials.update'),
)
const canManageAccess = computed(() => access.value?.canManageAccess ?? false)

const testing = ref(false)
const replacing = ref(false)
const updating = ref(false)
const archiving = ref(false)
const editOpen = ref(false)
const mutationError = ref('')
const lastTest = ref<ConnectionTestResult>()
const testFailed = ref(false)
const credentialForm = reactive<Record<string, string>>({})
const editConfiguration = reactive<Record<string, string>>({})
const editName = ref('')
const editDescription = ref('')
const hasCredentialChanges = computed(() => Object.values(credentialForm).some((value) => value.length > 0))
const tones: Record<ConnectionHealth, 'success' | 'warning' | 'danger' | 'neutral' | 'info'> = {
  healthy: 'success',
  degraded: 'warning',
  unhealthy: 'danger',
  unknown: 'neutral',
  testing: 'info',
}

function clearCredentialForm() {
  for (const key of Object.keys(credentialForm)) credentialForm[key] = ''
}
async function runTest() {
  testing.value = true
  mutationError.value = ''
  lastTest.value = undefined
  testFailed.value = false
  try {
    lastTest.value = await connectionService.test(id.value)
    await refetch()
    ui.pushToast({
      kind: lastTest.value.status === 'success' ? 'success' : 'error',
      title: lastTest.value.status === 'success' ? 'Connection healthy' : 'Connection test failed',
      message: lastTest.value.message ?? lastTest.value.error?.message,
    })
  } catch {
    testFailed.value = true
    mutationError.value = 'The connection test could not be completed.'
  } finally {
    testing.value = false
  }
}
let healthTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  healthTimer = setInterval(() => {
    if (!testing.value && document.visibilityState === 'visible') void refetch()
  }, 30_000)
})
onBeforeUnmount(() => {
  if (healthTimer) clearInterval(healthTimer)
})
async function replaceCredentials() {
  if (!connection.value || !hasCredentialChanges.value) return
  replacing.value = true
  mutationError.value = ''
  try {
    const values = Object.fromEntries(Object.entries(credentialForm).filter(([, value]) => value))
    await connectionService.replaceCredentials(connection.value.id, values, connection.value.version)
    clearCredentialForm()
    await refetch()
    ui.pushToast({
      kind: 'success',
      title: 'Credentials replaced',
      message: 'The prior credential version was revoked.',
    })
  } catch {
    mutationError.value = 'Credentials could not be replaced. Existing credentials remain unchanged.'
  } finally {
    clearCredentialForm()
    replacing.value = false
  }
}
function openEdit() {
  if (!connection.value) return
  editName.value = connection.value.name
  editDescription.value = connection.value.description
  for (const key of Object.keys(editConfiguration)) delete editConfiguration[key]
  for (const [key, value] of Object.entries(connection.value.configuration ?? {})) {
    editConfiguration[key] = String(value)
  }
  mutationError.value = ''
  editOpen.value = true
}
function typedConfiguration(): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(editConfiguration)) {
    const original = connection.value?.configuration?.[key]
    result[key] =
      typeof original === 'number' ? Number(value) : typeof original === 'boolean' ? value === 'true' : value
  }
  return result
}
async function saveEdit() {
  if (!connection.value || !editName.value.trim()) return
  updating.value = true
  mutationError.value = ''
  try {
    await connectionService.update(connection.value.id, {
      name: editName.value.trim(),
      description: editDescription.value.trim(),
      configuration: typedConfiguration(),
      version: connection.value.version,
    })
    await refetch()
    editOpen.value = false
    ui.pushToast({ kind: 'success', title: 'Connection updated', message: editName.value.trim() })
  } catch {
    mutationError.value = 'The connection could not be updated. Refresh and verify the configuration values.'
  } finally {
    updating.value = false
  }
}
async function archive() {
  archiving.value = true
  mutationError.value = ''
  try {
    await connectionService.archive(id.value)
    invalidateQueries('connections:')
    await router.replace('/connections')
  } catch {
    mutationError.value = 'The connection could not be archived.'
  } finally {
    archiving.value = false
  }
}
</script>

<template>
  <div class="detail">
    <div v-if="isLoading" class="detail__loading"><VipSpinner label="Loading connection…" /></div>
    <VipEmptyState
      v-else-if="!connection"
      icon="warning"
      tone="warning"
      title="Connection not found"
      description="It does not exist or is outside the current tenant."
      ><VipButton variant="primary" @click="router.push('/connections')">Back</VipButton></VipEmptyState
    >
    <template v-else>
      <VipAlert v-if="mutationError" tone="danger" title="Connection operation failed">
        {{ mutationError }}
        <VipButton v-if="testFailed" variant="ghost" size="xs" @click="runTest">Retry health test</VipButton>
      </VipAlert>
      <VipPageHeader :title="connection.name" :description="connection.description || connection.type.name">
        <template #status
          ><VipBadge :tone="tones[connection.health_status]" variant="soft">{{
            connection.health_status
          }}</VipBadge></template
        >
        <template #actions>
          <VipButton variant="tertiary" @click="router.push('/connections')">Back</VipButton>
          <VipButton v-if="canEdit" variant="secondary" @click="openEdit">Edit</VipButton>
          <VipButton v-if="canTest" variant="primary" icon="play" :loading="testing" @click="runTest"
            >Test connection</VipButton
          >
          <VipButton v-if="canManageAccess" variant="danger" :loading="archiving" @click="archive">Archive</VipButton>
          <ResourceShareButton
            v-if="canManageAccess"
            resource-type="connection"
            :resource-id="connection.id"
            :resource-name="connection.name"
            variant="secondary"
          />
        </template>
      </VipPageHeader>
      <div class="detail__grid">
        <VipCard
          ><h3>Safe configuration</h3>
          <dl>
            <div v-for="(value, key) in connection.configuration" :key="key">
              <dt>{{ String(key).replace(/_/g, ' ') }}</dt>
              <dd>{{ value }}</dd>
            </div>
          </dl></VipCard
        >
        <VipCard
          ><h3>Health</h3>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{{ connection.health_status }}</dd>
            </div>
            <div>
              <dt>Last tested</dt>
              <dd>{{ connection.last_tested_at ? formatDateTime(connection.last_tested_at) : 'Never' }}</dd>
            </div>
            <div>
              <dt>Latency</dt>
              <dd>
                {{ connection.last_test_latency_ms == null ? '—' : formatDuration(connection.last_test_latency_ms) }}
              </dd>
            </div>
            <div>
              <dt>Latest outcome</dt>
              <dd>
                {{ lastTest?.message ?? lastTest?.error?.message ?? connection.last_test_status ?? 'Not tested' }}
              </dd>
            </div>
          </dl></VipCard
        >
        <VipCard
          ><h3>Credentials</h3>
          <p>
            {{ connection.credentials_configured ? 'Configured' : 'Not configured' }} · version
            {{ connection.credential_version }}
          </p>
          <p class="detail__safe">Stored credentials are never returned or prefilled.</p>
          <form v-if="canRotate" class="detail__credentials" autocomplete="off" @submit.prevent="replaceCredentials">
            <VipInput
              v-for="(_state, key) in connection.secret_fields"
              :key="key"
              v-model="credentialForm[key]"
              :label="String(key).replace(/_/g, ' ')"
              type="password"
              autocomplete="new-password"
            /><VipButton variant="secondary" type="submit" :loading="replacing" :disabled="!hasCredentialChanges"
              >Replace credentials</VipButton
            >
          </form></VipCard
        >
        <VipCard
          ><h3>Metadata</h3>
          <dl>
            <div>
              <dt>Type</dt>
              <dd>{{ connection.type.name }}</dd>
            </div>
            <div>
              <dt>Connection ID</dt>
              <dd class="detail__mono">{{ connection.id }}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>{{ connection.version }}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{{ formatDateTime(connection.created_at) }}</dd>
            </div>
          </dl></VipCard
        >
      </div>

      <VipDialog :open="editOpen" title="Edit connection" size="md" @close="editOpen = false">
        <VipInput v-model="editName" label="Name" required maxlength="160" />
        <div class="detail__edit-field">
          <VipInput v-model="editDescription" label="Description" maxlength="1000" />
        </div>
        <h3 class="detail__edit-heading">Safe configuration</h3>
        <div v-for="(_value, key) in editConfiguration" :key="key" class="detail__edit-field">
          <VipInput v-model="editConfiguration[key]" :label="String(key).replace(/_/g, ' ')" required />
        </div>
        <VipAlert v-if="mutationError" tone="danger" title="Update failed">{{ mutationError }}</VipAlert>
        <template #footer>
          <VipButton variant="tertiary" :disabled="updating" @click="editOpen = false">Cancel</VipButton>
          <VipButton variant="primary" :loading="updating" :disabled="!editName.trim()" @click="saveEdit">
            Save changes
          </VipButton>
        </template>
      </VipDialog>
    </template>
  </div>
</template>

<style scoped>
.detail {
  max-width: 1100px;
  margin: 0 auto;
}
.detail__loading {
  display: flex;
  justify-content: center;
  padding: var(--vip-sp-12);
}
.detail__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-6);
}
h3 {
  margin-bottom: var(--vip-sp-5);
}
dl div {
  display: flex;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-3) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
dt,
.detail__safe {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
dd {
  text-align: right;
}
.detail__mono {
  font-family: var(--vip-font-mono);
}
.detail__credentials {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-5);
}
.detail__edit-field {
  margin-top: var(--vip-sp-4);
}
.detail__edit-heading {
  margin-top: var(--vip-sp-6);
  margin-bottom: 0;
}
@media (max-width: 800px) {
  .detail__grid {
    grid-template-columns: 1fr;
  }
}
</style>
