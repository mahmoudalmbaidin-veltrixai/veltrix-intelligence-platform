<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation } from '@/shared/lib/query'
import {
  developerService,
  API_SCOPES,
  WEBHOOK_EVENTS,
  type ApiKey,
  type Webhook,
  type WebhookDelivery,
} from './developer.service'
import { useUiStore } from '@/shared/stores/ui'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipCheckbox from '@/shared/ui/VipCheckbox.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const ui = useUiStore()
const tab = ref('overview')
const tabs = [
  { value: 'overview', label: 'Overview' },
  { value: 'keys', label: 'API Keys' },
  { value: 'webhooks', label: 'Webhooks' },
  { value: 'docs', label: 'Documentation' },
  { value: 'sdks', label: 'SDKs' },
]

const { data: keys, refetch: refetchKeys } = useQuery('dev:keys', () => developerService.listKeys())
const { data: webhooks } = useQuery('dev:webhooks', () => developerService.listWebhooks())
const { data: deliveries } = useQuery('dev:deliveries', () => developerService.listDeliveries())

/* create key flow */
const createOpen = ref(false)
const keyName = ref('')
const keyScopes = ref<string[]>([])
const revealedSecret = ref<string | null>(null)
const createMut = useMutation((p: { name: string; scopes: string[] }) => developerService.createKey(p), {
  onSuccess: ({ secret }) => {
    revealedSecret.value = secret
    refetchKeys()
  },
})
function toggleScope(s: string) {
  keyScopes.value = keyScopes.value.includes(s) ? keyScopes.value.filter((x) => x !== s) : [...keyScopes.value, s]
}
async function submitKey() {
  if (!keyName.value.trim()) return
  await createMut.mutate({ name: keyName.value, scopes: keyScopes.value })
}
function closeCreate() {
  createOpen.value = false
  revealedSecret.value = null
  keyName.value = ''
  keyScopes.value = []
}
function copySecret() {
  if (revealedSecret.value) navigator.clipboard?.writeText(revealedSecret.value)
  ui.pushToast({ kind: 'success', title: 'Secret copied' })
}

/* webhook create */
const webhookOpen = ref(false)
const webhookUrl = ref('')
const webhookEvents = ref<string[]>([])
function toggleEvent(e: string) {
  webhookEvents.value = webhookEvents.value.includes(e)
    ? webhookEvents.value.filter((x) => x !== e)
    : [...webhookEvents.value, e]
}
function createWebhook() {
  ui.pushToast({ kind: 'success', title: 'Webhook created', message: webhookUrl.value })
  webhookOpen.value = false
  webhookUrl.value = ''
  webhookEvents.value = []
}

function act(m: string) {
  ui.pushToast({ kind: 'info', title: m })
}

const keyColumns: Column<ApiKey>[] = [
  { key: 'name', label: 'Name' },
  { key: 'prefix', label: 'Prefix' },
  { key: 'scopes', label: 'Scopes' },
  { key: 'lastUsed', label: 'Last used' },
  { key: 'status', label: 'Status' },
  { key: 'actions', label: '', align: 'right' },
]
const whColumns: Column<Webhook>[] = [
  { key: 'url', label: 'Endpoint' },
  { key: 'events', label: 'Events' },
  { key: 'status', label: 'Status' },
  { key: 'lastDelivery', label: 'Last delivery' },
]
const dlvColumns: Column<WebhookDelivery>[] = [
  { key: 'event', label: 'Event' },
  { key: 'status', label: 'Status' },
  { key: 'responseCode', label: 'Code' },
  { key: 'ts', label: 'When' },
  { key: 'actions', label: '', align: 'right' },
]

const curlSample = `curl https://api.veltrix.com/v1/pipelines \\
  -H "Authorization: Bearer $VIP_API_KEY" \\
  -H "Content-Type: application/json"`
const jsSample = `import { VIPClient } from '@veltrix/sdk'

const vip = new VIPClient({ apiKey: process.env.VIP_API_KEY })
const runs = await vip.pipelines.run('pl_revenue')`
</script>

<template>
  <div>
    <VipPageHeader
      title="Developer Portal"
      description="API keys, webhooks, documentation and SDKs for building on VIP."
    />
    <VipTabs v-model="tab" :tabs="tabs" />

    <div class="dev">
      <!-- OVERVIEW -->
      <template v-if="tab === 'overview'">
        <div class="dev-grid">
          <VipCard>
            <h3 class="dev-h">Quick start</h3>
            <p class="dev-p">Authenticate with a bearer token, then call any workspace-scoped resource.</p>
            <pre class="dev-code">{{ curlSample }}</pre>
            <pre class="dev-code">{{ jsSample }}</pre>
          </VipCard>
          <VipCard>
            <h3 class="dev-h">Error reference</h3>
            <table class="dev-errtable">
              <tbody>
                <tr>
                  <td><code>401</code></td>
                  <td>Invalid or missing API key</td>
                </tr>
                <tr>
                  <td><code>403</code></td>
                  <td>Key lacks the required scope</td>
                </tr>
                <tr>
                  <td><code>404</code></td>
                  <td>Resource not found in this workspace</td>
                </tr>
                <tr>
                  <td><code>409</code></td>
                  <td>Conflict — resource is locked or being modified</td>
                </tr>
                <tr>
                  <td><code>429</code></td>
                  <td>Rate limit exceeded — back off and retry</td>
                </tr>
              </tbody>
            </table>
          </VipCard>
        </div>
      </template>

      <!-- KEYS -->
      <template v-else-if="tab === 'keys'">
        <div class="dev-actions">
          <VipButton variant="primary" icon="plus" @click="createOpen = true">Create key</VipButton>
        </div>
        <VipTable :columns="keyColumns" :rows="keys ?? []" :row-key="(r) => r.id">
          <template #cell-prefix="{ row }"
            ><code class="dev-mono">{{ row.prefix }}…</code></template
          >
          <template #cell-scopes="{ row }"
            ><span class="dev-muted">{{ row.scopes.length }} scopes</span></template
          >
          <template #cell-lastUsed="{ row }">{{ relativeTime(row.lastUsed) }}</template>
          <template #cell-status="{ row }"
            ><VipBadge :tone="row.status === 'active' ? 'success' : 'neutral'" size="sm">{{
              row.status
            }}</VipBadge></template
          >
          <template #cell-actions="{ row }">
            <div class="dev-row-actions">
              <VipButton
                variant="ghost"
                size="xs"
                icon="refresh"
                :disabled="row.status !== 'active'"
                @click="act('Key rotated')"
                >Rotate</VipButton
              >
              <VipButton
                variant="ghost"
                size="xs"
                icon="trash"
                :disabled="row.status !== 'active'"
                @click="act('Key revoked')"
                >Revoke</VipButton
              >
            </div>
          </template>
        </VipTable>
      </template>

      <!-- WEBHOOKS -->
      <template v-else-if="tab === 'webhooks'">
        <div class="dev-actions">
          <VipButton variant="primary" icon="plus" @click="webhookOpen = true">Create webhook</VipButton>
        </div>
        <VipTable :columns="whColumns" :rows="webhooks ?? []" :row-key="(r) => r.id">
          <template #cell-url="{ row }"
            ><code class="dev-mono">{{ row.url }}</code></template
          >
          <template #cell-events="{ row }"
            ><span class="dev-muted">{{ row.events.join(', ') }}</span></template
          >
          <template #cell-status="{ row }"
            ><VipBadge :tone="row.status === 'active' ? 'success' : 'neutral'" size="sm">{{
              row.status
            }}</VipBadge></template
          >
          <template #cell-lastDelivery="{ row }">{{ relativeTime(row.lastDelivery) }}</template>
        </VipTable>
        <h3 class="dev-h dev-h--mt">Delivery log</h3>
        <VipTable :columns="dlvColumns" :rows="deliveries ?? []" :row-key="(r) => r.id">
          <template #cell-status="{ row }"
            ><VipBadge :tone="row.status === 'success' ? 'success' : 'danger'" size="sm">{{
              row.status
            }}</VipBadge></template
          >
          <template #cell-ts="{ row }">{{ relativeTime(row.ts) }}</template>
          <template #cell-actions
            ><VipButton variant="ghost" size="xs" icon="refresh" @click="act('Delivery replayed')"
              >Replay</VipButton
            ></template
          >
        </VipTable>
      </template>

      <!-- DOCS -->
      <template v-else-if="tab === 'docs'">
        <VipCard>
          <h3 class="dev-h">Authentication</h3>
          <p class="dev-p">
            All requests require a bearer token in the <code>Authorization</code> header. Keys are workspace-scoped and
            carry explicit scopes.
          </p>
          <pre class="dev-code">Authorization: Bearer vip_live_xxx</pre>
          <h3 class="dev-h dev-h--mt">Base URL</h3>
          <pre class="dev-code">https://api.veltrix.com/v1</pre>
          <VipAlert tone="info" title="Interactive docs"
            >Full OpenAPI reference and a try-it console connect to the backend gateway.</VipAlert
          >
        </VipCard>
      </template>

      <!-- SDKS -->
      <template v-else>
        <div class="dev-grid">
          <VipCard
            v-for="sdk in [
              { n: 'TypeScript / JavaScript', c: 'npm install @veltrix/sdk' },
              { n: 'Python', c: 'pip install veltrix' },
              { n: 'Go', c: 'go get github.com/veltrix/vip-go' },
            ]"
            :key="sdk.n"
          >
            <h3 class="dev-h">{{ sdk.n }}</h3>
            <pre class="dev-code">{{ sdk.c }}</pre>
          </VipCard>
        </div>
        <VipAlert tone="info" title="Embedding foundation"
          >Signed embed tokens for dashboards and reports are issued by the backend embedding service.</VipAlert
        >
      </template>
    </div>

    <!-- create key dialog -->
    <VipDialog :open="createOpen" title="Create API key" @close="closeCreate">
      <template v-if="!revealedSecret">
        <VipInput v-model="keyName" label="Key name" placeholder="ci-deploy" required />
        <div class="dev-scopes">
          <div class="dev-scopes-label">Scopes</div>
          <VipCheckbox
            v-for="s in API_SCOPES"
            :key="s"
            :model-value="keyScopes.includes(s)"
            :label="s"
            @update:model-value="toggleScope(s)"
          />
        </div>
      </template>
      <template v-else>
        <VipAlert tone="warning" title="Copy your secret now"
          >This is the only time the full secret is shown. Store it securely — it cannot be retrieved again.</VipAlert
        >
        <div class="dev-secret">
          <code>{{ revealedSecret }}</code
          ><VipButton variant="secondary" size="sm" icon="copy" @click="copySecret">Copy</VipButton>
        </div>
      </template>
      <template #footer>
        <template v-if="!revealedSecret">
          <VipButton variant="tertiary" @click="closeCreate">Cancel</VipButton>
          <VipButton variant="primary" :loading="createMut.isPending.value" @click="submitKey">Create</VipButton>
        </template>
        <VipButton v-else variant="primary" @click="closeCreate">Done</VipButton>
      </template>
    </VipDialog>

    <!-- create webhook dialog -->
    <VipDialog :open="webhookOpen" title="Create webhook" @close="webhookOpen = false">
      <VipInput
        v-model="webhookUrl"
        label="Endpoint URL"
        placeholder="https://example.com/hook"
        icon="webhook"
        required
      />
      <div class="dev-scopes">
        <div class="dev-scopes-label">Events</div>
        <VipCheckbox
          v-for="e in WEBHOOK_EVENTS"
          :key="e"
          :model-value="webhookEvents.includes(e)"
          :label="e"
          @update:model-value="toggleEvent(e)"
        />
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="webhookOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :disabled="!webhookUrl" @click="createWebhook">Create</VipButton>
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.dev {
  margin-top: var(--vip-sp-7);
}
.dev-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-6);
}
.dev-h {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.dev-h--mt {
  margin-top: var(--vip-sp-7);
}
.dev-p {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin: var(--vip-sp-4) 0;
}
.dev-code {
  background: var(--vip-surface-inset);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-5);
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
  overflow-x: auto;
  margin-bottom: var(--vip-sp-4);
  white-space: pre;
}
.dev-errtable {
  width: 100%;
  font-size: var(--vip-fs-sm);
}
.dev-errtable td {
  padding: var(--vip-sp-3) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
  color: var(--vip-text-secondary);
}
.dev-errtable code {
  font-family: var(--vip-font-mono);
  color: var(--vip-danger-text);
  margin-right: var(--vip-sp-4);
}
.dev-actions {
  margin-bottom: var(--vip-sp-5);
}
.dev-mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-secondary);
}
.dev-muted {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.dev-row-actions {
  display: flex;
  gap: var(--vip-sp-2);
  justify-content: flex-end;
}
.dev-scopes {
  margin-top: var(--vip-sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.dev-scopes-label {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
}
.dev-secret {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-5);
  padding: var(--vip-sp-5);
  background: var(--vip-surface-inset);
  border-radius: var(--vip-radius-md);
}
.dev-secret code {
  flex: 1;
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  word-break: break-all;
}
</style>
