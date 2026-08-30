<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipTextarea from '@/shared/ui/VipTextarea.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const APP_VERSION = '0.1.0'
type Mode = 'support' | 'bug' | 'feature' | null

const route = useRoute()
const platform = usePlatformStore()
const ui = useUiStore()

const mode = ref<Mode>(null)
const form = reactive({ subject: '', message: '' })

const workspaceName = computed(() => {
  const list = (platform as unknown as { workspaces?: { id: string; name: string }[] }).workspaces ?? []
  const id = (platform as unknown as { workspaceId?: string | null }).workspaceId
  return list.find((w) => w.id === id)?.name ?? '—'
})

// Safe, non-sensitive diagnostic context for a bug report. Never includes
// passwords, tokens, secrets, connection strings, or dataset contents.
const context = computed(() => ({
  page: route.fullPath,
  workspace: workspaceName.value,
  browser: typeof navigator !== 'undefined' ? navigator.userAgent : '—',
  appVersion: APP_VERSION,
  timestamp: new Date().toISOString(),
}))

const dialogMeta = computed(() => {
  switch (mode.value) {
    case 'support':
      return {
        title: 'Contact Support',
        description: 'Describe what you need help with and we’ll prepare a message you can send.',
        submit: 'Copy message',
      }
    case 'bug':
      return {
        title: 'Report a Bug',
        description: 'Describe what happened. Non-sensitive context below is included automatically.',
        submit: 'Copy report',
      }
    case 'feature':
      return {
        title: 'Request a Feature',
        description: 'Tell us what would make Veltrix One more useful for you.',
        submit: 'Copy request',
      }
    default:
      return { title: '', description: '', submit: '' }
  }
})

function open(next: Exclude<Mode, null>) {
  form.subject = ''
  form.message = ''
  mode.value = next
}

function buildReport(): string {
  const lines = [
    `Type: ${dialogMeta.value.title}`,
    `Subject: ${form.subject || '(none)'}`,
    '',
    form.message || '(no description)',
  ]
  if (mode.value === 'bug') {
    lines.push(
      '',
      '--- Diagnostic context (non-sensitive) ---',
      `Page: ${context.value.page}`,
      `Workspace: ${context.value.workspace}`,
      `App version: ${context.value.appVersion}`,
      `Browser: ${context.value.browser}`,
      `Time: ${context.value.timestamp}`,
    )
  }
  return lines.join('\n')
}

async function submit() {
  if (!form.message.trim()) {
    ui.pushToast({ kind: 'warning', title: 'Add a description', message: 'Please describe your request first.' })
    return
  }
  const report = buildReport()
  try {
    await navigator.clipboard.writeText(report)
    ui.pushToast({
      kind: 'success',
      title: 'Copied to clipboard',
      message: 'Your message was prepared. Share it with your administrator or support contact.',
    })
  } catch {
    ui.pushToast({
      kind: 'info',
      title: 'Message prepared',
      message: 'Copy the details from the dialog to share with your administrator or support contact.',
    })
  }
  mode.value = null
}
</script>

<template>
  <VipCard class="help-support">
    <div class="help-support__inner">
      <div class="help-support__intro">
        <h2 class="help-support__title">Need more help?</h2>
        <p class="help-support__text">Can’t find what you’re looking for? We’re here to help.</p>
      </div>
      <div class="help-support__actions">
        <VipButton variant="secondary" icon="help" @click="open('support')">Contact Support</VipButton>
        <VipButton variant="secondary" icon="warning" @click="open('bug')">Report a Bug</VipButton>
        <VipButton variant="secondary" icon="star" @click="open('feature')">Request a Feature</VipButton>
      </div>
    </div>
  </VipCard>

  <VipDialog
    :open="mode !== null"
    :title="dialogMeta.title"
    :description="dialogMeta.description"
    size="md"
    @close="mode = null"
  >
    <div class="help-support__form">
      <VipInput v-model="form.subject" label="Subject" placeholder="Short summary" />
      <VipTextarea
        v-model="form.message"
        label="Description"
        :rows="5"
        placeholder="Describe your request in a few sentences…"
      />
      <div v-if="mode === 'bug'" class="help-support__context" aria-label="Included context">
        <p class="help-support__context-title"><VipIcon name="check" :size="14" /> Included automatically</p>
        <dl>
          <div>
            <dt>Page</dt>
            <dd>{{ context.page }}</dd>
          </div>
          <div>
            <dt>Workspace</dt>
            <dd>{{ context.workspace }}</dd>
          </div>
          <div>
            <dt>App version</dt>
            <dd>{{ context.appVersion }}</dd>
          </div>
          <div>
            <dt>Time</dt>
            <dd>{{ context.timestamp }}</dd>
          </div>
        </dl>
        <p class="help-support__context-note">No passwords, tokens, secrets, or data contents are included.</p>
      </div>
    </div>
    <template #footer>
      <VipButton variant="tertiary" @click="mode = null">Cancel</VipButton>
      <VipButton variant="primary" icon="check" @click="submit">{{ dialogMeta.submit }}</VipButton>
    </template>
  </VipDialog>
</template>

<style scoped>
.help-support__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-5);
  flex-wrap: wrap;
}
.help-support__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.help-support__text {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  margin-top: 2px;
}
.help-support__actions {
  display: flex;
  gap: var(--vip-sp-3);
  flex-wrap: wrap;
}
.help-support__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.help-support__context {
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-4);
  background: var(--vip-surface-2);
}
.help-support__context-title {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-secondary);
  margin-bottom: var(--vip-sp-3);
}
.help-support__context dl {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.help-support__context dl > div {
  display: flex;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  font-size: var(--vip-fs-xs);
}
.help-support__context dt {
  color: var(--vip-text-muted);
}
.help-support__context dd {
  color: var(--vip-text-secondary);
  text-align: right;
  word-break: break-all;
}
.help-support__context-note {
  margin-top: var(--vip-sp-3);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
@media (max-width: 600px) {
  .help-support__actions {
    width: 100%;
  }
}
</style>
