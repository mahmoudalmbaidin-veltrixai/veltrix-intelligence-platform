<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { connectionService, type ConnectionType, type JsonSchemaProperty } from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'

const router = useRouter()
const route = useRoute()
const ui = useUiStore()
const { data: types } = useQuery('connections:types', () => connectionService.types())
const typeKey = ref(String(route.query.type ?? ''))
const selected = computed<ConnectionType | undefined>(() =>
  types.value?.find((item) => item.key === typeKey.value && item.is_enabled),
)
const name = ref('')
const description = ref('')
const configuration = reactive<Record<string, string>>({})
const credentials = reactive<Record<string, string>>({})
const submitting = ref(false)
const error = ref('')

watch(
  selected,
  (value) => {
    error.value = ''
    for (const key of Object.keys(configuration)) delete configuration[key]
    for (const key of Object.keys(credentials)) delete credentials[key]
    for (const [key, property] of Object.entries(value?.configuration_schema.properties ?? {})) {
      configuration[key] = property.default == null ? '' : String(property.default)
    }
  },
  { immediate: true },
)
watch([typeKey, name, description, () => JSON.stringify(configuration), () => JSON.stringify(credentials)], () => {
  error.value = ''
})

function label(key: string, property: JsonSchemaProperty) {
  return property.title ?? key.replace(/_/g, ' ')
}
function typedConfiguration(): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(configuration)) {
    const property = selected.value?.configuration_schema.properties?.[key]
    result[key] = property?.type === 'integer' ? Number(value) : property?.type === 'boolean' ? value === 'true' : value
  }
  return result
}
function clearCredentials() {
  for (const key of Object.keys(credentials)) credentials[key] = ''
}
async function submit() {
  if (!selected.value) return
  submitting.value = true
  error.value = ''
  try {
    const connection = await connectionService.create({
      name: name.value,
      description: description.value,
      connection_type: selected.value.key,
      configuration: typedConfiguration(),
      credentials: Object.fromEntries(Object.entries(credentials).filter(([, value]) => value)),
    })
    clearCredentials()
    ui.pushToast({ kind: 'success', title: 'Connection created', message: 'Credentials were encrypted server-side.' })
    await router.replace(`/connections/${connection.id}`)
  } catch {
    error.value = 'The connection could not be created. Review the safe configuration and try again.'
    clearCredentials()
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="wizard">
    <VipPageHeader title="New connection" description="Credentials are write-only and are never returned by VIP." />
    <VipAlert v-if="error" tone="danger" title="Creation failed">{{ error }}</VipAlert>
    <VipCard>
      <form class="wizard__form" autocomplete="off" @submit.prevent="submit">
        <label
          >Connection type<select v-model="typeKey" required>
            <option value="" disabled>Select a type</option>
            <option v-for="item in types?.filter((type) => type.is_enabled)" :key="item.key" :value="item.key">
              {{ item.name }}
            </option>
          </select></label
        >
        <VipInput v-model="name" label="Name" required maxlength="160" />
        <VipInput v-model="description" label="Description" maxlength="1000" />
        <template v-if="selected">
          <h3>Configuration</h3>
          <VipInput
            v-for="(property, key) in selected.configuration_schema.properties"
            :key="key"
            v-model="configuration[key]"
            :label="label(String(key), property)"
            :required="selected.configuration_schema.required?.includes(String(key))"
          />
          <h3>Credentials</h3>
          <p class="wizard__safe">
            Sensitive values remain only in this form until submission and are cleared immediately afterward.
          </p>
          <VipInput
            v-for="(property, key) in selected.secret_schema.properties"
            :key="key"
            v-model="credentials[key]"
            :label="label(String(key), property)"
            type="password"
            autocomplete="new-password"
          />
        </template>
        <div class="wizard__actions">
          <VipButton variant="tertiary" type="button" @click="router.push('/connections')">Cancel</VipButton
          ><VipButton variant="primary" type="submit" :loading="submitting" :disabled="!selected"
            >Create securely</VipButton
          >
        </div>
      </form>
    </VipCard>
  </div>
</template>

<style scoped>
.wizard {
  max-width: 760px;
  margin: 0 auto;
}
.wizard__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.wizard__form label {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
}
.wizard__form select {
  padding: var(--vip-sp-4);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-1);
  color: var(--vip-text-primary);
}
.wizard__safe {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.wizard__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--vip-sp-3);
  margin-top: var(--vip-sp-5);
}
</style>
