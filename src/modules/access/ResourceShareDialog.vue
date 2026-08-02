<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { accessService, type Principal, type ResourceEntry } from './access.service'
import { useUiStore } from '@/shared/stores/ui'
import { formatDateTime } from '@/shared/lib/format'
import { safeErrorText } from '@/shared/lib/safeError'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipAvatar from '@/shared/ui/VipAvatar.vue'

const props = defineProps<{
  open: boolean
  resourceType: string
  resourceId: string
  resourceName?: string
  levels: string[]
  canManage?: boolean
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const ui = useUiStore()

const entries = ref<ResourceEntry[]>([])
const loading = ref(false)
const listError = ref<string | null>(null)

async function refresh() {
  if (!props.resourceType || !props.resourceId) return
  loading.value = true
  listError.value = null
  try {
    entries.value = await accessService.listResourceAccess(props.resourceType, props.resourceId)
  } catch (e) {
    listError.value = safeErrorText(e)
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.resourceType, props.resourceId],
  ([isOpen]) => {
    if (isOpen) {
      resetForm()
      void refresh()
    }
  },
  { immediate: true },
)

// --- principal search ---
const query = ref('')
const results = ref<Principal[]>([])
const searching = ref(false)
const selected = ref<Principal | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

watch(query, (value) => {
  selected.value = null
  if (searchTimer) clearTimeout(searchTimer)
  const q = value.trim()
  if (q.length < 2) {
    results.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    searching.value = true
    try {
      results.value = await accessService.searchPrincipals(q)
    } catch {
      results.value = []
    } finally {
      searching.value = false
    }
  }, 250)
})

function choose(principal: Principal) {
  selected.value = principal
  query.value = principal.label
  results.value = []
}

// --- grant form ---
const level = ref('')
const effect = ref('allow')
const expiry = ref('never')
const granting = ref(false)
const grantError = ref<string | null>(null)

const levelOptions = computed(() => props.levels.map((l) => ({ value: l, label: titleCase(l) })))

watch(
  () => props.levels,
  (levels) => {
    if (!level.value && levels.length) level.value = levels[0]
  },
  { immediate: true },
)

function resetForm() {
  query.value = ''
  results.value = []
  selected.value = null
  effect.value = 'allow'
  expiry.value = 'never'
  grantError.value = null
  level.value = props.levels[0] ?? ''
}

function expiryIso(): string | null {
  if (expiry.value === 'never') return null
  const days = Number(expiry.value)
  return new Date(Date.now() + days * 86_400_000).toISOString()
}

async function submitGrant() {
  if (!selected.value || !level.value || granting.value) return
  granting.value = true
  grantError.value = null
  try {
    await accessService.grantResourceAccess(props.resourceType, props.resourceId, {
      subject_type: selected.value.principal_type,
      subject_id: selected.value.id,
      access_level: level.value,
      effect: effect.value as 'allow' | 'deny',
      expires_at: expiryIso(),
    })
    ui.pushToast({
      kind: 'success',
      title: effect.value === 'deny' ? 'Access denied' : 'Access granted',
      message: `${selected.value.label} · ${titleCase(level.value)}`,
    })
    resetForm()
    await refresh()
  } catch (e) {
    grantError.value = safeErrorText(e)
  } finally {
    granting.value = false
  }
}

// --- revoke ---
const revokingId = ref<string | null>(null)
async function revoke(entry: ResourceEntry) {
  revokingId.value = entry.id
  try {
    await accessService.revokeResourceAccess(props.resourceType, props.resourceId, entry.id)
    ui.pushToast({ kind: 'success', title: 'Access revoked', message: entry.subject_label })
    await refresh()
  } catch (e) {
    ui.pushToast({ kind: 'error', title: 'Revoke failed', message: safeErrorText(e) })
  } finally {
    revokingId.value = null
  }
}

function titleCase(value: string): string {
  return value.replace(/(^|_)([a-z])/g, (_m, _p, c: string) => (_p ? ' ' : '') + c.toUpperCase())
}
function expired(entry: ResourceEntry): boolean {
  return !!entry.expires_at && new Date(entry.expires_at).getTime() < Date.now()
}

const manageable = computed(() => props.canManage !== false)
</script>

<template>
  <VipDialog :open="open" :title="`Share ${resourceName ?? titleCase(resourceType)}`" size="md" @close="emit('close')">
    <div class="share">
      <section v-if="manageable" class="share-add">
        <h3 class="share-h">Add people or groups</h3>
        <div class="share-search">
          <VipInput
            v-model="query"
            icon="search"
            placeholder="Search users and groups by name or email"
            autocomplete="off"
          />
          <ul v-if="results.length" class="share-results" role="listbox">
            <li v-for="p in results" :key="`${p.principal_type}:${p.id}`">
              <button type="button" class="share-result" @click="choose(p)">
                <VipAvatar :name="p.label" :size="26" />
                <span class="share-result__text">
                  <span class="share-result__label">{{ p.label }}</span>
                  <span v-if="p.detail" class="share-result__detail">{{ p.detail }}</span>
                </span>
                <VipBadge size="sm" :tone="p.principal_type === 'group' ? 'info' : 'neutral'">
                  {{ p.principal_type }}
                </VipBadge>
              </button>
            </li>
          </ul>
          <p v-else-if="query.trim().length >= 2 && !searching" class="share-empty">No matches found.</p>
        </div>

        <div v-if="selected" class="share-form">
          <div class="share-selected">
            <VipAvatar :name="selected.label" :size="24" />
            <span>{{ selected.label }}</span>
            <VipBadge size="sm" :tone="selected.principal_type === 'group' ? 'info' : 'neutral'">
              {{ selected.principal_type }}
            </VipBadge>
          </div>
          <div class="share-controls">
            <VipSelect v-model="level" label="Access level" :options="levelOptions" />
            <VipSelect
              v-model="effect"
              label="Effect"
              :options="[
                { value: 'allow', label: 'Allow' },
                { value: 'deny', label: 'Deny (overrides)' },
              ]"
            />
            <VipSelect
              v-model="expiry"
              label="Expires"
              :options="[
                { value: 'never', label: 'Never' },
                { value: '7', label: 'In 7 days' },
                { value: '30', label: 'In 30 days' },
                { value: '90', label: 'In 90 days' },
              ]"
            />
          </div>
          <VipAlert v-if="grantError" tone="danger" title="Could not save">{{ grantError }}</VipAlert>
          <div class="share-form__actions">
            <VipButton variant="primary" :loading="granting" icon="plus" @click="submitGrant">
              {{ effect === 'deny' ? 'Add deny rule' : 'Grant access' }}
            </VipButton>
          </div>
        </div>
      </section>

      <section class="share-list">
        <h3 class="share-h">People &amp; groups with access</h3>
        <VipAlert v-if="listError" tone="danger" title="Could not load access list">{{ listError }}</VipAlert>
        <p v-if="loading" class="share-empty">Loading…</p>
        <p v-else-if="!entries.length" class="share-empty">
          No explicit grants yet. Access is governed by roles and ownership.
        </p>
        <ul v-else class="share-entries">
          <li v-for="entry in entries" :key="entry.id" class="share-entry">
            <VipAvatar :name="entry.subject_label" :size="30" />
            <div class="share-entry__text">
              <div class="share-entry__label">
                {{ entry.subject_label }}
                <VipBadge v-if="entry.subject_type === 'group'" size="sm" tone="info">group</VipBadge>
              </div>
              <div class="share-entry__meta">
                <span v-if="entry.subject_detail">{{ entry.subject_detail }}</span>
                <span v-if="entry.expires_at" :class="{ 'is-expired': expired(entry) }">
                  · {{ expired(entry) ? 'Expired' : 'Expires' }} {{ formatDateTime(entry.expires_at) }}
                </span>
              </div>
            </div>
            <VipBadge size="sm" :tone="entry.effect === 'deny' ? 'danger' : 'success'">
              {{ entry.effect === 'deny' ? 'Deny' : 'Allow' }} · {{ titleCase(entry.access_level) }}
            </VipBadge>
            <button
              v-if="manageable"
              class="share-revoke"
              :disabled="revokingId === entry.id"
              :aria-label="`Revoke access for ${entry.subject_label}`"
              @click="revoke(entry)"
            >
              <VipIcon name="trash" :size="15" />
            </button>
          </li>
        </ul>
      </section>
    </div>

    <template #footer>
      <VipButton variant="tertiary" @click="emit('close')">Done</VipButton>
    </template>
  </VipDialog>
</template>

<style scoped>
.share {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.share-h {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-secondary);
  margin-bottom: var(--vip-sp-3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.share-search {
  position: relative;
}
.share-results {
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
.share-result {
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
.share-result:hover {
  background: var(--vip-surface-hover);
}
.share-result__text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.share-result__label {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.share-result__detail {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.share-empty {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  padding: var(--vip-sp-2) 0;
}
.share-form {
  margin-top: var(--vip-sp-4);
  padding: var(--vip-sp-4);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-subtle);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.share-selected {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-weight: var(--vip-fw-medium);
}
.share-controls {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--vip-sp-3);
}
.share-form__actions {
  display: flex;
  justify-content: flex-end;
}
.share-entries {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.share-entry {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-3);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.share-entry__text {
  flex: 1;
  min-width: 0;
}
.share-entry__label {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.share-entry__meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.is-expired {
  color: var(--vip-danger-text, var(--vip-text-muted));
}
.share-revoke {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid transparent;
  border-radius: var(--vip-radius-md);
  background: none;
  color: var(--vip-text-secondary);
  cursor: pointer;
}
.share-revoke:hover:not(:disabled) {
  background: var(--vip-surface-hover);
  border-color: var(--vip-border);
  color: var(--vip-danger-text, var(--vip-text-primary));
}
@media (max-width: 640px) {
  .share-controls {
    grid-template-columns: 1fr;
  }
}
</style>
