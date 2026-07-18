<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { relativeTime } from '@/shared/lib/format'
import { aiService, AI_MODELS, type ChatMessage, type ChatSource } from './ai.service'
import VipButton from '@/shared/ui/VipButton.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipTooltip from '@/shared/ui/VipTooltip.vue'
import VipSpinner from '@/shared/ui/VipSpinner.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'

const { data: conversations, isLoading: loadingConvs } = useQuery('ai:conversations', () =>
  aiService.listConversations(),
)
const { data: knowledge } = useQuery('ai:knowledge', () => aiService.listKnowledge())

const activeConvId = ref<string | null>(null)
const messages = ref<ChatMessage[]>([])
const loadingThread = ref(false)

const draft = ref('')
const streaming = ref(false)
const model = ref('veltrix-analyst')
const knowledgeCtx = ref('kb_finance')
const threadEl = ref<HTMLElement>()
let controller: AbortController | undefined

const modelOptions = AI_MODELS
const knowledgeOptions = computed(() => [
  { value: 'none', label: 'No knowledge base' },
  ...(knowledge.value ?? []).map((k) => ({ value: k.id, label: k.name })),
])

const monthlyUsagePct = 68
const isEmptyThread = computed(() => messages.value.length === 0 && !loadingThread.value)

async function scrollToEnd(): Promise<void> {
  await nextTick()
  if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight
}

async function selectConversation(id: string): Promise<void> {
  if (streaming.value) stopGeneration()
  activeConvId.value = id
  loadingThread.value = true
  messages.value = []
  const thread = await aiService.getMessages(id)
  messages.value = thread
  loadingThread.value = false
  void scrollToEnd()
}

function newConversation(): void {
  if (streaming.value) stopGeneration()
  activeConvId.value = null
  messages.value = []
}

function stopGeneration(): void {
  controller?.abort()
  controller = undefined
  streaming.value = false
}

async function send(): Promise<void> {
  const text = draft.value.trim()
  if (!text || streaming.value) return

  const userMsg: ChatMessage = {
    id: `u_${Date.now()}`,
    role: 'user',
    content: text,
    ts: new Date().toISOString(),
  }
  const assistantMsg: ChatMessage = {
    id: `a_${Date.now()}`,
    role: 'assistant',
    content: '',
    ts: new Date().toISOString(),
    toolCalls: [{ name: 'semantic-search', status: 'running', summary: 'Grounding against selected knowledge base' }],
  }
  messages.value.push(userMsg, assistantMsg)
  draft.value = ''
  streaming.value = true
  controller = new AbortController()
  void scrollToEnd()

  const target = messages.value[messages.value.length - 1]
  const result: { sources: ChatSource[] } = await aiService.streamReply(
    text,
    (chunk) => {
      target.content += chunk
      void scrollToEnd()
    },
    controller.signal,
  )

  if (target.toolCalls) target.toolCalls = target.toolCalls.map((t) => ({ ...t, status: 'done' }))
  if (result.sources.length) target.sources = result.sources
  streaming.value = false
  controller = undefined
  void scrollToEnd()
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    void send()
  }
}
</script>

<template>
  <div class="asst">
    <!-- Conversation list -->
    <aside class="asst__side">
      <div class="asst__side-head">
        <div class="asst__brand">
          <span class="asst__brand-mark"><VipIcon name="sparkles" :size="16" /></span>
          <span class="asst__brand-name">VIP Assistant</span>
        </div>
        <VipButton variant="primary" size="sm" icon="plus" block @click="newConversation"> New conversation </VipButton>
      </div>
      <div class="asst__conv-list">
        <div v-if="loadingConvs" class="asst__loading"><VipSpinner label="Loading conversations" /></div>
        <button
          v-for="c in conversations"
          :key="c.id"
          type="button"
          class="asst__conv"
          :class="{ 'is-active': c.id === activeConvId }"
          @click="selectConversation(c.id)"
        >
          <VipIcon name="clock" :size="14" class="asst__conv-icon" />
          <span class="asst__conv-body">
            <span class="asst__conv-title">{{ c.title }}</span>
            <span class="asst__conv-meta">{{ c.messageCount }} messages · {{ relativeTime(c.updatedAt) }}</span>
          </span>
        </button>
      </div>
      <div class="asst__side-foot">
        <div class="asst__usage">
          <div class="asst__usage-row">
            <span>AI usage this month</span>
            <span>{{ monthlyUsagePct }}%</span>
          </div>
          <div class="asst__usage-bar"><span :style="{ width: `${monthlyUsagePct}%` }" /></div>
        </div>
      </div>
    </aside>

    <!-- Chat main -->
    <div class="asst__main">
      <header class="asst__top">
        <div class="asst__top-info">
          <h1 class="asst__top-title">{{ activeConvId ? 'Conversation' : 'New conversation' }}</h1>
          <VipBadge tone="brand" variant="soft" size="sm">Grounded chat</VipBadge>
        </div>
        <div class="asst__top-ctx">
          <VipSelect v-model="model" :options="modelOptions" size="sm" />
          <VipSelect v-model="knowledgeCtx" :options="knowledgeOptions" size="sm" />
        </div>
      </header>

      <div ref="threadEl" class="asst__thread">
        <div v-if="loadingThread" class="asst__loading"><VipSpinner label="Loading thread" /></div>

        <VipEmptyState
          v-else-if="isEmptyThread"
          icon="sparkles"
          title="Ask anything about your data"
          description="Query metrics, explain lineage, or draft a summary. Answers are grounded in your selected knowledge base and cite their sources."
        />

        <template v-else>
          <div v-for="m in messages" :key="m.id" class="asst__msg" :class="`is-${m.role}`">
            <div class="asst__avatar" :class="`is-${m.role}`">
              <VipIcon :name="m.role === 'user' ? 'users' : 'sparkles'" :size="14" />
            </div>
            <div class="asst__bubble-wrap">
              <div class="asst__bubble">
                <div v-if="m.toolCalls?.length" class="asst__tools">
                  <span v-for="t in m.toolCalls" :key="t.name" class="asst__tool" :class="`is-${t.status}`">
                    <VipIcon :name="t.status === 'running' ? 'refresh' : 'check'" :size="11" />
                    <span class="asst__tool-name">{{ t.name }}</span>
                    <VipTooltip :text="t.summary"><VipIcon name="info" :size="11" /></VipTooltip>
                  </span>
                </div>
                <p v-if="m.content" class="asst__text">{{ m.content }}</p>
                <span v-else-if="streaming && m.role === 'assistant'" class="asst__caret" />
                <div v-if="m.sources?.length" class="asst__sources">
                  <span class="asst__sources-label">Sources</span>
                  <div class="asst__source-chips">
                    <VipBadge v-for="s in m.sources" :key="s.ref" tone="neutral" variant="outline" size="sm">
                      <VipIcon name="link" :size="10" /> {{ s.title }}
                    </VipBadge>
                  </div>
                </div>
              </div>
              <span class="asst__time">{{ relativeTime(m.ts) }}</span>
            </div>
          </div>
        </template>
      </div>

      <div class="asst__composer">
        <div class="asst__notice">
          <VipIcon name="info" :size="12" />
          AI responses can be inaccurate — verify important figures against the cited sources before acting.
        </div>
        <div class="asst__input-row">
          <textarea
            v-model="draft"
            class="asst__input"
            rows="1"
            placeholder="Message the assistant…  (Enter to send, Shift+Enter for newline)"
            @keydown="onKeydown"
          />
          <div class="asst__input-actions">
            <VipButton v-if="streaming" variant="secondary" size="sm" icon="close" @click="stopGeneration">
              Stop
            </VipButton>
            <VipButton variant="primary" size="sm" icon="play" :disabled="!draft.trim() || streaming" @click="send">
              Send
            </VipButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.asst {
  display: grid;
  grid-template-columns: 288px 1fr;
  height: 100vh;
  background: var(--vip-bg-app);
  color: var(--vip-text-primary);
}

/* Sidebar */
.asst__side {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--vip-border);
  background: var(--vip-surface-1);
  min-height: 0;
}
.asst__side-head {
  padding: var(--vip-sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
  border-bottom: 1px solid var(--vip-border-subtle);
}
.asst__brand {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}
.asst__brand-mark {
  width: 28px;
  height: 28px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.asst__brand-name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.asst__conv-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--vip-sp-4);
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
}
.asst__conv {
  display: flex;
  gap: var(--vip-sp-4);
  align-items: flex-start;
  width: 100%;
  text-align: left;
  padding: var(--vip-sp-4) var(--vip-sp-5);
  background: none;
  border: none;
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
}
.asst__conv:hover {
  background: var(--vip-surface-hover);
}
.asst__conv.is-active {
  background: var(--vip-brand-soft);
}
.asst__conv-icon {
  margin-top: 2px;
  color: var(--vip-text-muted);
  flex: none;
}
.asst__conv-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.asst__conv-title {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.asst__conv-meta {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
}
.asst__side-foot {
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-top: 1px solid var(--vip-border-subtle);
}
.asst__usage {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.asst__usage-row {
  display: flex;
  justify-content: space-between;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.asst__usage-bar {
  height: 5px;
  border-radius: var(--vip-radius-full);
  background: var(--vip-surface-3);
  overflow: hidden;
}
.asst__usage-bar span {
  display: block;
  height: 100%;
  background: var(--vip-brand-500);
  border-radius: var(--vip-radius-full);
}

/* Main */
.asst__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.asst__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-6);
  padding: var(--vip-sp-5) var(--vip-sp-8);
  border-bottom: 1px solid var(--vip-border-subtle);
  background: var(--vip-surface-1);
}
.asst__top-info {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
}
.asst__top-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.asst__top-ctx {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
}

.asst__thread {
  flex: 1;
  overflow-y: auto;
  padding: var(--vip-sp-8);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-7);
  min-height: 0;
}
.asst__loading {
  display: flex;
  justify-content: center;
  padding: var(--vip-sp-9);
}

.asst__msg {
  display: flex;
  gap: var(--vip-sp-5);
  max-width: 820px;
}
.asst__msg.is-user {
  flex-direction: row-reverse;
  margin-left: auto;
}
.asst__avatar {
  width: 30px;
  height: 30px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-full);
}
.asst__avatar.is-assistant {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.asst__avatar.is-user {
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.asst__bubble-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
  min-width: 0;
}
.asst__msg.is-user .asst__bubble-wrap {
  align-items: flex-end;
}
.asst__bubble {
  padding: var(--vip-sp-5) var(--vip-sp-6);
  border-radius: var(--vip-radius-lg);
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-subtle);
}
.asst__msg.is-user .asst__bubble {
  background: var(--vip-brand-soft);
  border-color: transparent;
}
.asst__text {
  font-size: var(--vip-fs-md);
  line-height: var(--vip-lh-normal);
  color: var(--vip-text-primary);
  white-space: pre-wrap;
}
.asst__caret {
  display: inline-block;
  width: 7px;
  height: 15px;
  background: var(--vip-brand-500);
  border-radius: 1px;
  animation: asst-blink 1s steps(2) infinite;
}
@keyframes asst-blink {
  0%,
  50% {
    opacity: 1;
  }
  50.01%,
  100% {
    opacity: 0;
  }
}

.asst__tools {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3);
  margin-bottom: var(--vip-sp-4);
}
.asst__tool {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  padding: 2px var(--vip-sp-4);
  border-radius: var(--vip-radius-full);
  font-size: var(--vip-fs-2xs);
  background: var(--vip-surface-3);
  color: var(--vip-text-muted);
}
.asst__tool.is-running {
  background: var(--vip-info-soft);
  color: var(--vip-info-text);
}
.asst__tool.is-done {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.asst__tool-name {
  font-family: var(--vip-font-mono);
}

.asst__sources {
  margin-top: var(--vip-sp-5);
  padding-top: var(--vip-sp-5);
  border-top: 1px dashed var(--vip-border);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.asst__sources-label {
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-muted);
}
.asst__source-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3);
}
.asst__time {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
  padding: 0 var(--vip-sp-3);
}

/* Composer */
.asst__composer {
  border-top: 1px solid var(--vip-border-subtle);
  padding: var(--vip-sp-5) var(--vip-sp-8) var(--vip-sp-6);
  background: var(--vip-surface-1);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.asst__notice {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
}
.asst__input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--vip-sp-5);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-lg);
  padding: var(--vip-sp-4) var(--vip-sp-4) var(--vip-sp-4) var(--vip-sp-6);
}
.asst__input-row:focus-within {
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.asst__input {
  flex: 1;
  min-width: 0;
  resize: none;
  max-height: 160px;
  background: none;
  border: none;
  outline: none;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-md);
  line-height: var(--vip-lh-normal);
  font-family: var(--vip-font-sans);
  padding: var(--vip-sp-3) 0;
}
.asst__input::placeholder {
  color: var(--vip-text-disabled);
}
.asst__input-actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  flex: none;
}
</style>
