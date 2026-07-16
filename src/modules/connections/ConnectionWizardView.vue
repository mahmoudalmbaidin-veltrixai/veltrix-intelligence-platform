<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMutation } from '@/shared/lib/query'
import { useUiStore } from '@/shared/stores/ui'
import { formatDuration } from '@/shared/lib/format'
import {
  connectionService,
  CONNECTOR_ICON,
  CONNECTOR_LABEL,
  type ConnectorKind,
  type ConnectionTestResult,
  type Connection,
  type CreateConnectionPayload,
} from './connections.service'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipCheckbox from '@/shared/ui/VipCheckbox.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'

const router = useRouter()
const ui = useUiStore()

type StepKey = 'connector' | 'configure' | 'credentials' | 'test' | 'resources' | 'review'
interface StepDef {
  key: StepKey
  label: string
  description: string
}

const STEPS: StepDef[] = [
  { key: 'connector', label: 'Connector', description: 'Choose a source type' },
  { key: 'configure', label: 'Configure', description: 'Name and connection details' },
  { key: 'credentials', label: 'Credentials', description: 'Authentication' },
  { key: 'test', label: 'Test', description: 'Verify connectivity' },
  { key: 'resources', label: 'Resources', description: 'Select what to sync' },
  { key: 'review', label: 'Review', description: 'Confirm and create' },
]

const stepIndex = ref(0)
const currentStep = computed<StepDef>(() => STEPS[stepIndex.value])

const CONNECTOR_OPTIONS: { value: ConnectorKind; label: string }[] = (
  ['postgres', 'mysql', 'sqlserver', 'csv', 'excel', 'rest', 's3'] as ConnectorKind[]
).map((k) => ({ value: k, label: CONNECTOR_LABEL[k] }))

const fileConnectors: ConnectorKind[] = ['csv', 'excel']
const apiConnectors: ConnectorKind[] = ['rest']
const storageConnectors: ConnectorKind[] = ['s3']

interface WizardState {
  connector: ConnectorKind | ''
  name: string
  owner: string
  host: string
  port: string
  database: string
  username: string
  password: string
  apiKey: string
  bucket: string
}

const form = reactive<WizardState>({
  connector: '',
  name: '',
  owner: 'Data Platform',
  host: '',
  port: '',
  database: '',
  username: '',
  password: '',
  apiKey: '',
  bucket: '',
})

const isFile = computed(() => form.connector !== '' && fileConnectors.includes(form.connector))
const isApi = computed(() => form.connector !== '' && apiConnectors.includes(form.connector))
const isStorage = computed(() => form.connector !== '' && storageConnectors.includes(form.connector))
const isDatabase = computed(
  () => form.connector !== '' && !isFile.value && !isApi.value && !isStorage.value,
)

/* ---- resource selection (mock discovery) ---- */
interface ResourceOption { id: string; label: string; type: string }
const resourceCatalog: Record<'database' | 'api' | 'storage' | 'file', ResourceOption[]> = {
  database: [
    { id: 'public.orders', label: 'public.orders', type: 'table' },
    { id: 'public.customers', label: 'public.customers', type: 'table' },
    { id: 'public.invoices', label: 'public.invoices', type: 'table' },
    { id: 'public.products', label: 'public.products', type: 'table' },
    { id: 'analytics.daily_revenue', label: 'analytics.daily_revenue', type: 'view' },
  ],
  api: [
    { id: '/events', label: '/events', type: 'endpoint' },
    { id: '/contacts', label: '/contacts', type: 'endpoint' },
    { id: '/campaigns', label: '/campaigns', type: 'endpoint' },
  ],
  storage: [
    { id: 'raw/orders/', label: 'raw/orders/*.parquet', type: 'prefix' },
    { id: 'raw/clickstream/', label: 'raw/clickstream/*.json', type: 'prefix' },
    { id: 'exports/finance/', label: 'exports/finance/*.csv', type: 'prefix' },
  ],
  file: [{ id: 'uploaded', label: 'Uploaded file', type: 'file' }],
}

const resourceKind = computed<'database' | 'api' | 'storage' | 'file'>(() => {
  if (isApi.value) return 'api'
  if (isStorage.value) return 'storage'
  if (isFile.value) return 'file'
  return 'database'
})
const availableResources = computed(() => resourceCatalog[resourceKind.value])
const selectedResources = ref<string[]>([])

function toggleResource(id: string, on: boolean) {
  if (on) selectedResources.value = [...new Set([...selectedResources.value, id])]
  else selectedResources.value = selectedResources.value.filter((r) => r !== id)
}

/* ---- test step ---- */
const testing = ref(false)
const testResult = ref<ConnectionTestResult | undefined>(undefined)

async function runTest() {
  testing.value = true
  testResult.value = undefined
  await new Promise((r) => setTimeout(r, 700 + Math.random() * 800))
  // Deterministic mock: fail if host contains "fail", otherwise succeed.
  const ok = !/fail|invalid/i.test(form.host + form.name)
  testResult.value = ok
    ? { ok: true, latencyMs: 40 + Math.round(Math.random() * 180), message: 'Connection established and credentials verified.' }
    : { ok: false, latencyMs: 0, message: 'Authentication failed — check host and credentials, then retry.' }
  testing.value = false
}

/* ---- per-step validation ---- */
function stepValid(key: StepKey): boolean {
  switch (key) {
    case 'connector':
      return form.connector !== ''
    case 'configure': {
      if (!form.name.trim() || !form.owner.trim()) return false
      if (isDatabase.value) return !!form.host.trim() && !!form.database.trim()
      if (isApi.value) return !!form.host.trim()
      if (isStorage.value) return !!form.bucket.trim()
      return true // file upload
    }
    case 'credentials':
      if (isDatabase.value) return !!form.username.trim() && !!form.password.trim()
      if (isApi.value) return !!form.apiKey.trim()
      return true
    case 'test':
      return testResult.value?.ok === true
    case 'resources':
      if (isFile.value) return true
      return selectedResources.value.length > 0
    case 'review':
      return true
  }
}

const canAdvance = computed(() => stepValid(currentStep.value.key))

function next() {
  if (!canAdvance.value) return
  if (stepIndex.value < STEPS.length - 1) stepIndex.value++
}
function back() {
  if (stepIndex.value > 0) stepIndex.value--
}
function goTo(i: number) {
  // Only allow jumping to a step whose predecessors are all valid.
  if (i <= stepIndex.value) {
    stepIndex.value = i
    return
  }
  for (let s = 0; s < i; s++) {
    if (!stepValid(STEPS[s].key)) return
  }
  stepIndex.value = i
}

/* ---- create ---- */
const createConnection = useMutation<CreateConnectionPayload, Connection>(
  (payload) => connectionService.create(payload),
  {
    invalidate: ['connections:list'],
    onSuccess: (conn) => {
      ui.pushToast({ kind: 'success', title: 'Connection created', message: `${conn.name} is now available.` })
      router.push('/connections')
    },
    onError: (err) => {
      ui.pushToast({ kind: 'error', title: 'Could not create connection', message: err.message })
    },
  },
)

async function submit() {
  if (form.connector === '') return
  const hostOrEndpoint = isStorage.value ? `s3://${form.bucket}` : form.host || undefined
  await createConnection.mutate({
    name: form.name.trim(),
    connector: form.connector,
    host: hostOrEndpoint,
    owner: form.owner.trim(),
  })
}

const summaryEndpoint = computed(() => {
  if (isStorage.value) return form.bucket ? `s3://${form.bucket}` : '—'
  if (isDatabase.value) return form.host ? `${form.host}${form.port ? ':' + form.port : ''}` : '—'
  return form.host || '—'
})
</script>

<template>
  <div class="wiz">
    <VipPageHeader
      title="New connection"
      description="Connect a new data source in a few guided steps."
    >
      <template #actions>
        <VipButton variant="tertiary" icon="close" @click="router.push('/connections')">
          Cancel
        </VipButton>
      </template>
    </VipPageHeader>

    <div class="wiz__layout">
      <!-- step indicator -->
      <ol class="wiz__steps">
        <li
          v-for="(s, i) in STEPS"
          :key="s.key"
          class="wiz__step"
          :class="{ 'is-active': i === stepIndex, 'is-done': i < stepIndex }"
          @click="goTo(i)"
        >
          <span class="wiz__step-marker">
            <VipIcon v-if="i < stepIndex" name="check" :size="13" :stroke-width="3" />
            <span v-else>{{ i + 1 }}</span>
          </span>
          <span class="wiz__step-text">
            <span class="wiz__step-label">{{ s.label }}</span>
            <span class="wiz__step-desc">{{ s.description }}</span>
          </span>
        </li>
      </ol>

      <!-- step body -->
      <VipCard class="wiz__panel">
        <!-- STEP 1: connector -->
        <section v-if="currentStep.key === 'connector'" class="wiz__section">
          <h2 class="wiz__heading">Select a connector</h2>
          <p class="wiz__lead">Pick the type of source you want to connect.</p>
          <div class="wiz__connector-grid">
            <button
              v-for="opt in CONNECTOR_OPTIONS"
              :key="opt.value"
              type="button"
              class="wiz__connector"
              :class="{ 'is-selected': form.connector === opt.value }"
              @click="form.connector = opt.value"
            >
              <span class="wiz__connector-icon"><VipIcon :name="CONNECTOR_ICON[opt.value]" :size="20" /></span>
              <span class="wiz__connector-label">{{ opt.label }}</span>
              <VipIcon v-if="form.connector === opt.value" name="check" :size="15" class="wiz__connector-check" />
            </button>
          </div>
        </section>

        <!-- STEP 2: configure -->
        <section v-else-if="currentStep.key === 'configure'" class="wiz__section">
          <h2 class="wiz__heading">Configure connection</h2>
          <p class="wiz__lead">Give the connection a name and provide its location.</p>
          <div class="wiz__form">
            <VipInput v-model="form.name" label="Connection name" required placeholder="e.g. Core Warehouse" />
            <VipInput v-model="form.owner" label="Owner / team" required placeholder="e.g. Data Platform" />

            <template v-if="isDatabase">
              <VipInput v-model="form.host" label="Host" required placeholder="db.internal.example.com" />
              <VipInput v-model="form.port" label="Port" placeholder="5432" />
              <VipInput v-model="form.database" label="Database" required placeholder="warehouse" />
            </template>

            <template v-else-if="isApi">
              <VipInput v-model="form.host" label="Base URL" required placeholder="https://api.example.com" />
            </template>

            <template v-else-if="isStorage">
              <VipInput v-model="form.bucket" label="Bucket" required placeholder="my-data-bucket" prefix="s3://" />
            </template>

            <template v-else>
              <VipAlert tone="info" title="File upload">
                In a live environment you would upload the file here. In mock mode we simulate a
                previously uploaded workbook.
              </VipAlert>
            </template>
          </div>
        </section>

        <!-- STEP 3: credentials -->
        <section v-else-if="currentStep.key === 'credentials'" class="wiz__section">
          <h2 class="wiz__heading">Credentials</h2>
          <p class="wiz__lead">Provide the authentication details used to connect.</p>
          <VipAlert tone="info" title="Your secrets are safe">
            Secrets are never persisted in mock mode. They are used only for the connectivity test
            and discarded immediately afterwards.
          </VipAlert>
          <div class="wiz__form wiz__form--spaced">
            <template v-if="isDatabase">
              <VipInput v-model="form.username" label="Username" required placeholder="svc_analytics" />
              <VipInput v-model="form.password" type="password" label="Password" required placeholder="••••••••" />
            </template>
            <template v-else-if="isApi">
              <VipInput v-model="form.apiKey" type="password" label="API key" required placeholder="sk_live_…" />
            </template>
            <template v-else-if="isStorage">
              <VipInput v-model="form.username" type="password" label="Access key ID" required placeholder="AKIA…" />
              <VipInput v-model="form.password" type="password" label="Secret access key" required placeholder="••••••••" />
            </template>
            <template v-else>
              <VipAlert tone="success" title="No credentials required">
                Uploaded files do not require authentication.
              </VipAlert>
            </template>
          </div>
        </section>

        <!-- STEP 4: test -->
        <section v-else-if="currentStep.key === 'test'" class="wiz__section">
          <h2 class="wiz__heading">Test connection</h2>
          <p class="wiz__lead">Run a connectivity check before continuing.</p>

          <div class="wiz__test">
            <VipButton variant="primary" icon="play" :loading="testing" @click="runTest">
              {{ testResult ? 'Run test again' : 'Run test' }}
            </VipButton>

            <div v-if="testing" class="wiz__test-progress">
              <VipSpinner />
              <span>Connecting to {{ summaryEndpoint }}…</span>
            </div>

            <div v-else-if="testResult" class="wiz__test-result" :class="testResult.ok ? 'is-ok' : 'is-fail'">
              <span class="wiz__test-icon">
                <VipIcon :name="testResult.ok ? 'success' : 'error'" :size="18" />
              </span>
              <div class="wiz__test-body">
                <div class="wiz__test-title">
                  {{ testResult.ok ? 'Connection successful' : 'Connection failed' }}
                  <VipBadge v-if="testResult.ok" tone="success" variant="soft" size="sm">
                    {{ formatDuration(testResult.latencyMs) }}
                  </VipBadge>
                </div>
                <p class="wiz__test-msg">{{ testResult.message }}</p>
                <p v-if="!testResult.ok" class="wiz__test-hint">
                  Tip: in mock mode a host or name containing "fail" simulates an error.
                </p>
              </div>
            </div>

            <VipAlert v-else tone="info">
              Click “Run test” to validate connectivity using the details you provided.
            </VipAlert>
          </div>
        </section>

        <!-- STEP 5: resources -->
        <section v-else-if="currentStep.key === 'resources'" class="wiz__section">
          <h2 class="wiz__heading">Select resources</h2>
          <p class="wiz__lead">Choose the {{ resourceKind === 'database' ? 'tables and views' : 'resources' }} to make available.</p>
          <div class="wiz__resources">
            <label
              v-for="r in availableResources"
              :key="r.id"
              class="wiz__resource"
              :class="{ 'is-checked': selectedResources.includes(r.id) }"
            >
              <VipCheckbox
                :model-value="selectedResources.includes(r.id)"
                @update:model-value="(v: boolean) => toggleResource(r.id, v)"
              />
              <span class="wiz__resource-label">{{ r.label }}</span>
              <VipBadge tone="neutral" variant="soft" size="sm">{{ r.type }}</VipBadge>
            </label>
          </div>
        </section>

        <!-- STEP 6: review -->
        <section v-else class="wiz__section">
          <h2 class="wiz__heading">Review &amp; create</h2>
          <p class="wiz__lead">Confirm the details below, then create the connection.</p>
          <dl class="wiz__review">
            <div class="wiz__review-row">
              <dt>Connector</dt>
              <dd>{{ form.connector ? CONNECTOR_LABEL[form.connector] : '—' }}</dd>
            </div>
            <div class="wiz__review-row"><dt>Name</dt><dd>{{ form.name || '—' }}</dd></div>
            <div class="wiz__review-row"><dt>Owner</dt><dd>{{ form.owner || '—' }}</dd></div>
            <div class="wiz__review-row"><dt>Endpoint</dt><dd class="is-mono">{{ summaryEndpoint }}</dd></div>
            <div v-if="isDatabase" class="wiz__review-row"><dt>Database</dt><dd>{{ form.database || '—' }}</dd></div>
            <div class="wiz__review-row">
              <dt>Connectivity</dt>
              <dd>
                <VipBadge :tone="testResult?.ok ? 'success' : 'warning'" variant="soft" size="sm">
                  {{ testResult?.ok ? 'Verified' : 'Not tested' }}
                </VipBadge>
              </dd>
            </div>
            <div class="wiz__review-row">
              <dt>Resources</dt>
              <dd>
                <template v-if="isFile">Uploaded file</template>
                <template v-else>{{ selectedResources.length }} selected</template>
              </dd>
            </div>
          </dl>
          <VipAlert tone="warning" title="Secrets not stored">
            Credentials entered in this wizard are not saved in mock mode.
          </VipAlert>
        </section>

        <!-- footer nav -->
        <footer class="wiz__footer">
          <VipButton variant="tertiary" icon="chevronLeft" :disabled="stepIndex === 0" @click="back">
            Back
          </VipButton>
          <div class="wiz__footer-right">
            <span class="wiz__progress">Step {{ stepIndex + 1 }} of {{ STEPS.length }}</span>
            <VipButton
              v-if="currentStep.key !== 'review'"
              variant="primary"
              icon-right="chevronRight"
              :disabled="!canAdvance"
              @click="next"
            >
              Continue
            </VipButton>
            <VipButton
              v-else
              variant="primary"
              icon="check"
              :loading="createConnection.isPending.value"
              @click="submit"
            >
              Create connection
            </VipButton>
          </div>
        </footer>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.wiz { max-width: 1100px; margin: 0 auto; }
.wiz__layout { display: grid; grid-template-columns: 240px 1fr; gap: var(--vip-sp-8); align-items: start; }

.wiz__steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--vip-sp-2); }
.wiz__step {
  display: flex; align-items: center; gap: var(--vip-sp-5);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  border-radius: var(--vip-radius-md);
  cursor: pointer;
}
.wiz__step:hover { background: var(--vip-surface-hover); }
.wiz__step.is-active { background: var(--vip-brand-soft); }
.wiz__step-marker {
  width: 26px; height: 26px; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  border: 1px solid var(--vip-border-strong);
  background: var(--vip-surface-2);
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
}
.wiz__step.is-active .wiz__step-marker { background: var(--vip-brand-500); border-color: var(--vip-brand-500); color: var(--vip-text-on-brand); }
.wiz__step.is-done .wiz__step-marker { background: var(--vip-success); border-color: var(--vip-success); color: #fff; }
.wiz__step-text { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.wiz__step-label { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.wiz__step-desc { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); }

.wiz__panel { display: flex; flex-direction: column; }
.wiz__section { display: flex; flex-direction: column; gap: var(--vip-sp-5); }
.wiz__heading { font-size: var(--vip-fs-xl); font-weight: var(--vip-fw-semibold); }
.wiz__lead { font-size: var(--vip-fs-md); color: var(--vip-text-muted); margin-top: calc(-1 * var(--vip-sp-3)); }

.wiz__connector-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: var(--vip-sp-5); }
.wiz__connector {
  position: relative;
  display: flex; flex-direction: column; align-items: flex-start; gap: var(--vip-sp-4);
  padding: var(--vip-sp-6);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  text-align: left;
  transition: border-color var(--vip-motion-fast), background var(--vip-motion-fast);
}
.wiz__connector:hover { border-color: var(--vip-border-strong); }
.wiz__connector.is-selected { border-color: var(--vip-brand-500); background: var(--vip-brand-soft); }
.wiz__connector-icon {
  width: 36px; height: 36px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-3); color: var(--vip-text-secondary);
}
.wiz__connector.is-selected .wiz__connector-icon { background: var(--vip-brand-500); color: var(--vip-text-on-brand); }
.wiz__connector-label { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-medium); color: var(--vip-text-primary); }
.wiz__connector-check { position: absolute; top: var(--vip-sp-4); right: var(--vip-sp-4); color: var(--vip-brand-text); }

.wiz__form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vip-sp-6); }
.wiz__form--spaced { grid-template-columns: 1fr; max-width: 440px; }

.wiz__test { display: flex; flex-direction: column; gap: var(--vip-sp-5); align-items: flex-start; }
.wiz__test-progress { display: flex; align-items: center; gap: var(--vip-sp-4); color: var(--vip-text-secondary); font-size: var(--vip-fs-md); }
.wiz__test-result {
  display: flex; gap: var(--vip-sp-5); width: 100%;
  padding: var(--vip-sp-6);
  border-radius: var(--vip-radius-md);
  border: 1px solid var(--vip-border);
}
.wiz__test-result.is-ok { background: var(--vip-success-soft); border-color: transparent; }
.wiz__test-result.is-fail { background: var(--vip-danger-soft); border-color: transparent; }
.wiz__test-icon { flex: none; }
.wiz__test-result.is-ok .wiz__test-icon { color: var(--vip-success-text); }
.wiz__test-result.is-fail .wiz__test-icon { color: var(--vip-danger-text); }
.wiz__test-title { display: flex; align-items: center; gap: var(--vip-sp-4); font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); color: var(--vip-text-primary); }
.wiz__test-msg { font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); margin-top: var(--vip-sp-3); }
.wiz__test-hint { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: var(--vip-sp-3); }

.wiz__resources { display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.wiz__resource {
  display: flex; align-items: center; gap: var(--vip-sp-5);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  cursor: pointer;
}
.wiz__resource:hover { background: var(--vip-surface-hover); }
.wiz__resource.is-checked { border-color: var(--vip-brand-500); background: var(--vip-brand-soft); }
.wiz__resource-label { flex: 1; font-family: var(--vip-font-mono); font-size: var(--vip-fs-sm); color: var(--vip-text-primary); }

.wiz__review { display: flex; flex-direction: column; gap: 0; border: 1px solid var(--vip-border-subtle); border-radius: var(--vip-radius-md); overflow: hidden; }
.wiz__review-row { display: flex; justify-content: space-between; gap: var(--vip-sp-6); padding: var(--vip-sp-5) var(--vip-sp-6); }
.wiz__review-row:not(:last-child) { border-bottom: 1px solid var(--vip-border-subtle); }
.wiz__review-row dt { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }
.wiz__review-row dd { font-size: var(--vip-fs-md); color: var(--vip-text-primary); font-weight: var(--vip-fw-medium); text-align: right; }
.wiz__review-row dd.is-mono { font-family: var(--vip-font-mono); font-weight: var(--vip-fw-regular); }

.wiz__footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: var(--vip-sp-8);
  padding-top: var(--vip-sp-6);
  border-top: 1px solid var(--vip-border-subtle);
}
.wiz__footer-right { display: flex; align-items: center; gap: var(--vip-sp-5); }
.wiz__progress { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); }

@media (max-width: 860px) {
  .wiz__layout { grid-template-columns: 1fr; }
  .wiz__steps { flex-direction: row; overflow-x: auto; }
  .wiz__step-text { display: none; }
  .wiz__form { grid-template-columns: 1fr; }
}
</style>
