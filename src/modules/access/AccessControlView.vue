<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { accessService, type EffectiveAccess, type Principal, type ResourceTypeInfo } from './access.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { formatDateTime } from '@/shared/lib/format'
import { safeErrorText } from '@/shared/lib/safeError'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipAvatar from '@/shared/ui/VipAvatar.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import ResourceShareDialog from './ResourceShareDialog.vue'
import ResourcePicker from './ResourcePicker.vue'

const platform = usePlatformStore()
const canManage = computed(() => platform.can('resource.permissions.manage'))

const types = ref<ResourceTypeInfo[]>([])
const typesError = ref<string | null>(null)
onMounted(async () => {
  try {
    types.value = await accessService.listResourceTypes()
    if (types.value.length) resourceType.value = types.value[0].resource_type
  } catch (e) {
    typesError.value = safeErrorText(e)
  }
})

const typeOptions = computed(() =>
  types.value.map((t) => ({ value: t.resource_type, label: titleCase(t.resource_type) })),
)
const levelsForSelected = computed(() => types.value.find((t) => t.resource_type === resourceType.value)?.levels ?? [])

// --- inspector target ---
const resourceType = ref('')
const resourceId = ref('')
const resourceName = ref('')
const manualEntry = ref(false)
const shareOpen = ref(false)

function onResourceSelect(item: { id: string; name: string }) {
  resourceName.value = item.name
}
watch(resourceType, () => {
  resourceId.value = ''
  resourceName.value = ''
  result.value = null
})

function openShare() {
  if (resourceId.value.trim()) shareOpen.value = true
}

// --- simulate ---
const subjectQuery = ref('')
const subjectResults = ref<Principal[]>([])
const subjectSearching = ref(false)
const subject = ref<Principal | null>(null)
let subjectTimer: ReturnType<typeof setTimeout> | null = null

watch(subjectQuery, (value) => {
  subject.value = null
  if (subjectTimer) clearTimeout(subjectTimer)
  const q = value.trim()
  if (q.length < 2) {
    subjectResults.value = []
    return
  }
  subjectTimer = setTimeout(async () => {
    subjectSearching.value = true
    try {
      const all = await accessService.searchPrincipals(q)
      subjectResults.value = all.filter((p) => p.principal_type === 'user')
    } catch {
      subjectResults.value = []
    } finally {
      subjectSearching.value = false
    }
  }, 250)
})
function chooseSubject(p: Principal) {
  subject.value = p
  subjectQuery.value = p.label
  subjectResults.value = []
}

const result = ref<EffectiveAccess | null>(null)
const simulating = ref(false)
const simulateError = ref<string | null>(null)

async function runSimulate() {
  if (!resourceType.value || !resourceId.value.trim() || !subject.value) return
  simulating.value = true
  simulateError.value = null
  result.value = null
  try {
    result.value = await accessService.simulateAccess(resourceType.value, resourceId.value.trim(), subject.value.id)
    evaluatedAt.value = new Date().toISOString()
  } catch (e) {
    simulateError.value = safeErrorText(e)
  } finally {
    simulating.value = false
  }
}

const REASON_TEXT: Record<string, string> = {
  SUBJECT_SUSPENDED: 'The user or their membership is suspended, so access is denied before anything else.',
  EXPLICIT_DENY: 'An explicit deny rule applies and overrides every grant, including super-admin.',
  SUPER_ADMIN_OVERRIDE: 'The user is a platform super-admin and is allowed (deny rules still win over this).',
  WORKSPACE_ARCHIVED: 'The workspace is archived, which blocks non super-admin access.',
  OWNER: 'The user owns this resource and has every access level.',
  GRANTED: 'Access is granted by a resource ACL and/or an assigned role.',
  GRANT_EXPIRED: 'The only matching grant has expired and is ignored.',
  NO_GRANT: 'No role, ownership, or resource grant covers the requested level.',
}
function reasonText(reason: string): string {
  return REASON_TEXT[reason] ?? reason
}
const evaluatedAt = ref('')
function titleCase(value: string): string {
  return value.replace(/(^|_)([a-z])/g, (_m, _p, c: string) => (_p ? ' ' : '') + c.toUpperCase())
}
</script>

<template>
  <div>
    <VipPageHeader
      title="Access Control"
      description="Share resources with people and groups, then inspect exactly what access they resolve to."
    />

    <VipAlert v-if="typesError" tone="danger" title="Access catalog unavailable">{{ typesError }}</VipAlert>

    <!-- Permission matrix reference -->
    <section class="ac-card">
      <h2 class="ac-h">Permission matrix</h2>
      <p class="ac-sub">Access ladders for each governed resource type. Higher levels include everything below.</p>
      <ul class="ac-matrix">
        <li v-for="t in types" :key="t.resource_type" class="ac-matrix__row">
          <div class="ac-matrix__type">
            <VipIcon name="shield" :size="15" />
            {{ titleCase(t.resource_type) }}
          </div>
          <div class="ac-matrix__levels">
            <VipBadge v-for="lvl in t.levels" :key="lvl" tone="neutral" size="sm">{{ titleCase(lvl) }}</VipBadge>
          </div>
        </li>
      </ul>
    </section>

    <!-- Inspector -->
    <section class="ac-card">
      <h2 class="ac-h">Resource inspector</h2>
      <p class="ac-sub">Pick a resource to manage sharing or simulate a user's effective access.</p>
      <div class="ac-target">
        <VipSelect v-model="resourceType" label="Resource type" :options="typeOptions" />
        <div class="ac-picker">
          <span class="ac-picker__label">Resource</span>
          <ResourcePicker
            v-if="!manualEntry"
            v-model="resourceId"
            :resource-type="resourceType"
            @select="onResourceSelect"
          />
          <VipInput v-else v-model="resourceId" placeholder="00000000-0000-0000-0000-000000000000" />
          <button type="button" class="ac-picker__toggle" @click="manualEntry = !manualEntry">
            {{ manualEntry ? 'Search instead' : 'Enter ID manually' }}
          </button>
        </div>
        <VipButton variant="secondary" icon="share" :disabled="!resourceId.trim() || !canManage" @click="openShare">
          Manage sharing
        </VipButton>
      </div>

      <div class="ac-sim">
        <h3 class="ac-h3">Simulate effective access</h3>
        <div class="ac-search">
          <VipInput v-model="subjectQuery" icon="search" placeholder="Search a user to simulate" autocomplete="off" />
          <ul v-if="subjectResults.length" class="ac-results">
            <li v-for="p in subjectResults" :key="p.id">
              <button type="button" class="ac-result" @click="chooseSubject(p)">
                <VipAvatar :name="p.label" :size="26" />
                <span class="ac-result__text">
                  <span class="ac-result__label">{{ p.label }}</span>
                  <span v-if="p.detail" class="ac-result__detail">{{ p.detail }}</span>
                </span>
              </button>
            </li>
          </ul>
        </div>
        <div class="ac-sim__actions">
          <VipButton
            variant="primary"
            icon="eye"
            :loading="simulating"
            :disabled="!subject || !resourceId.trim()"
            @click="runSimulate"
          >
            Simulate access
          </VipButton>
        </div>

        <VipAlert v-if="simulateError" tone="danger" title="Simulation failed">{{ simulateError }}</VipAlert>

        <div v-if="result" class="ac-result-card">
          <div class="ac-result-card__head">
            <span class="ac-result-card__level">
              <VipBadge :tone="result.level ? 'success' : 'danger'" size="md">
                {{ result.level ? titleCase(result.level) : 'No access' }}
              </VipBadge>
            </span>
            <span class="ac-result-card__source">via {{ result.source }}</span>
          </div>
          <p class="ac-result-card__reason">{{ reasonText(result.reason) }}</p>
          <dl class="ac-breakdown">
            <div>
              <dt>Subject</dt>
              <dd>{{ subject?.label ?? result.user_id }}</dd>
            </div>
            <div>
              <dt>Decision code</dt>
              <dd>
                <code>{{ result.reason }}</code>
              </dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{{ result.source }}</dd>
            </div>
            <div v-if="evaluatedAt">
              <dt>Evaluated</dt>
              <dd>{{ formatDateTime(evaluatedAt) }}</dd>
            </div>
          </dl>
          <div v-if="result.allowed_levels.length" class="ac-result-card__ladder">
            <span class="ac-result-card__ladder-label">Allowed levels:</span>
            <VipBadge v-for="lvl in result.allowed_levels" :key="lvl" tone="brand" size="sm">
              {{ titleCase(lvl) }}
            </VipBadge>
          </div>
        </div>
      </div>
    </section>

    <ResourceShareDialog
      :open="shareOpen"
      :resource-type="resourceType"
      :resource-id="resourceId.trim()"
      :resource-name="resourceName || undefined"
      :levels="levelsForSelected"
      :can-manage="canManage"
      @close="shareOpen = false"
    />
  </div>
</template>

<style scoped>
.ac-card {
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-lg);
  background: var(--vip-surface);
  padding: var(--vip-sp-6);
  margin-bottom: var(--vip-sp-6);
}
.ac-h {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.ac-h3 {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
  margin-bottom: var(--vip-sp-3);
}
.ac-sub {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin: var(--vip-sp-2) 0 var(--vip-sp-5);
}
.ac-matrix {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.ac-matrix__row {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
}
.ac-matrix__type {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
  min-width: 160px;
}
.ac-matrix__levels {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-2);
}
.ac-target {
  display: grid;
  grid-template-columns: 220px 1fr auto;
  gap: var(--vip-sp-4);
  align-items: end;
}
.ac-sim {
  margin-top: var(--vip-sp-6);
  padding-top: var(--vip-sp-6);
  border-top: 1px solid var(--vip-border);
}
.ac-search {
  position: relative;
  max-width: 460px;
}
.ac-results {
  list-style: none;
  margin: var(--vip-sp-2) 0 0;
  padding: var(--vip-sp-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface);
  box-shadow: var(--vip-shadow-md);
  max-height: 200px;
  overflow-y: auto;
}
.ac-result {
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
.ac-result:hover {
  background: var(--vip-surface-hover);
}
.ac-result__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.ac-result__label {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
}
.ac-result__detail {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.ac-sim__actions {
  margin-top: var(--vip-sp-4);
}
.ac-result-card {
  margin-top: var(--vip-sp-5);
  padding: var(--vip-sp-5);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-subtle);
}
.ac-result-card__head {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
}
.ac-result-card__source {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.ac-result-card__reason {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin: var(--vip-sp-3) 0;
}
.ac-picker {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-1);
}
.ac-picker__label {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
}
.ac-picker__toggle {
  align-self: flex-start;
  background: none;
  border: none;
  padding: 0;
  font-size: var(--vip-fs-xs);
  color: var(--vip-accent-text, var(--vip-text-secondary));
  cursor: pointer;
}
.ac-breakdown {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--vip-sp-2) var(--vip-sp-4);
  margin: var(--vip-sp-3) 0;
}
.ac-breakdown div {
  display: flex;
  flex-direction: column;
}
.ac-breakdown dt {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.ac-breakdown dd {
  margin: 0;
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
}
.ac-result-card__ladder {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--vip-sp-2);
}
.ac-result-card__ladder-label {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
@media (max-width: 720px) {
  .ac-target {
    grid-template-columns: 1fr;
  }
}
</style>
