/**
 * AI module service (mock).
 *
 * Provides conversations, assistants, knowledge bases, agents and agent runs,
 * plus a simulated streaming reply for the assistant chat surface.
 *
 * INTEGRATION POINT:
 *   GET  /api/v1/ai/conversations
 *   GET  /api/v1/ai/conversations/:id/messages
 *   GET  /api/v1/ai/assistants
 *   GET  /api/v1/ai/knowledge
 *   GET  /api/v1/ai/agents
 *   GET  /api/v1/ai/agent-runs
 *   GET  /api/v1/ai/agent-runs/:id
 *   POST /api/v1/ai/chat            (SSE / streamed tokens)  -> replace streamReply()
 */
import { latency, isoAgo } from '@/shared/lib/mock'

export interface Conversation {
  id: string
  title: string
  updatedAt: string
  messageCount: number
}

export interface ChatSource {
  title: string
  ref: string
}

export interface ChatToolCall {
  name: string
  status: 'running' | 'done'
  summary: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: string
  sources?: ChatSource[]
  toolCalls?: ChatToolCall[]
}

export type PublishStatus = 'draft' | 'published'

export interface Assistant {
  id: string
  name: string
  description: string
  model: string
  status: PublishStatus
  instructions: string
  tools: string[]
  knowledge: string[]
}

export type KnowledgeStatus = 'ready' | 'indexing' | 'error'

export interface KnowledgeBase {
  id: string
  name: string
  documents: number
  status: KnowledgeStatus
  lastIndexed: string
}

export interface Agent {
  id: string
  name: string
  goal: string
  model: string
  status: PublishStatus
  tools: string[]
}

export type AgentRunStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface AgentRunStep {
  name: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  tool?: string
}

export interface AgentRun {
  id: string
  agent: string
  status: AgentRunStatus
  startedAt: string
  durationMs?: number
  tokens?: number
  cost?: number
  steps: AgentRunStep[]
}

/** Selectable models exposed across the AI surfaces. */
export const AI_MODELS: { value: string; label: string }[] = [
  { value: 'veltrix-reasoning-pro', label: 'Veltrix Reasoning Pro' },
  { value: 'veltrix-reasoning', label: 'Veltrix Reasoning' },
  { value: 'veltrix-fast', label: 'Veltrix Fast' },
  { value: 'veltrix-analyst', label: 'Veltrix Analyst' },
]

/** Tools that assistants / agents can be granted. */
export const AI_TOOLS: { value: string; label: string; icon: string }[] = [
  { value: 'sql-query', label: 'SQL query', icon: 'database' },
  { value: 'semantic-search', label: 'Semantic search', icon: 'search' },
  { value: 'dashboard-read', label: 'Dashboard reader', icon: 'chart' },
  { value: 'pipeline-trigger', label: 'Pipeline trigger', icon: 'workflow' },
  { value: 'web-fetch', label: 'Web fetch', icon: 'external' },
  { value: 'report-generator', label: 'Report generator', icon: 'report' },
]

const CONVERSATIONS: Conversation[] = [
  { id: 'cv_1', title: 'Q3 revenue variance by region', updatedAt: isoAgo(8), messageCount: 14 },
  { id: 'cv_2', title: 'Why did churn spike in June?', updatedAt: isoAgo(52), messageCount: 9 },
  { id: 'cv_3', title: 'Explain the fct_orders lineage', updatedAt: isoAgo(180), messageCount: 6 },
  { id: 'cv_4', title: 'Draft exec summary for board deck', updatedAt: isoAgo(1440), messageCount: 22 },
  { id: 'cv_5', title: 'Data quality incidents this week', updatedAt: isoAgo(2880), messageCount: 4 },
]

const MESSAGES: Record<string, ChatMessage[]> = {
  cv_1: [
    {
      id: 'm1',
      role: 'user',
      content: 'Break down Q3 revenue variance versus plan by region.',
      ts: isoAgo(14),
    },
    {
      id: 'm2',
      role: 'assistant',
      content:
        'Q3 revenue landed at $48.2M, 3.1% below the $49.7M plan. EMEA drove most of the gap (-$1.9M, primarily enterprise renewals slipping into Q4), partially offset by APAC over-performing (+$0.6M) on new logo expansion. NA was on plan within 0.4%.',
      ts: isoAgo(13),
      toolCalls: [
        { name: 'semantic-search', status: 'done', summary: 'Matched metric "net_revenue" in Sales Analytics model' },
        { name: 'sql-query', status: 'done', summary: 'Aggregated revenue by region for Q3 plan vs actual' },
      ],
      sources: [
        { title: 'Sales Analytics — net_revenue', ref: 'semantic:sm_sales/net_revenue' },
        { title: 'fct_revenue_daily', ref: 'dataset:ds_revenue_daily' },
        { title: 'Q3 Plan (Finance)', ref: 'doc:kb_finance/q3-plan' },
      ],
    },
  ],
}

const ASSISTANTS: Assistant[] = [
  {
    id: 'as_analyst',
    name: 'Revenue Analyst',
    description: 'Answers revenue, pipeline and forecast questions grounded in the Sales Analytics model.',
    model: 'veltrix-analyst',
    status: 'published',
    instructions:
      'You are a revenue analyst. Always ground answers in the Sales Analytics semantic model. Cite datasets. If a metric is ambiguous, ask a clarifying question before computing.',
    tools: ['sql-query', 'semantic-search', 'dashboard-read'],
    knowledge: ['kb_finance', 'kb_semantic'],
  },
  {
    id: 'as_support',
    name: 'Data Catalog Guide',
    description: 'Helps users discover datasets, understand lineage and locate the right owner.',
    model: 'veltrix-fast',
    status: 'published',
    instructions:
      'Help users navigate the data catalog. Prefer linking to lineage and owners over speculation. Never expose row-level data.',
    tools: ['semantic-search'],
    knowledge: ['kb_catalog'],
  },
  {
    id: 'as_exec',
    name: 'Executive Briefer',
    description: 'Drafts concise executive narratives from dashboards and reports.',
    model: 'veltrix-reasoning-pro',
    status: 'draft',
    instructions:
      'Write board-ready, neutral-tone narratives. Lead with the headline, then drivers, then risks. Keep to under 200 words unless asked.',
    tools: ['dashboard-read', 'report-generator'],
    knowledge: ['kb_finance'],
  },
]

const KNOWLEDGE: KnowledgeBase[] = [
  { id: 'kb_finance', name: 'Finance & Planning', documents: 342, status: 'ready', lastIndexed: isoAgo(90) },
  { id: 'kb_semantic', name: 'Semantic Model Docs', documents: 128, status: 'ready', lastIndexed: isoAgo(220) },
  { id: 'kb_catalog', name: 'Data Catalog', documents: 1874, status: 'indexing', lastIndexed: isoAgo(15) },
  { id: 'kb_policies', name: 'Governance Policies', documents: 56, status: 'ready', lastIndexed: isoAgo(1440) },
  { id: 'kb_runbooks', name: 'Ops Runbooks', documents: 73, status: 'error', lastIndexed: isoAgo(4320) },
]

const AGENTS: Agent[] = [
  {
    id: 'ag_freshness',
    name: 'Freshness Sentinel',
    goal: 'Detect stale critical datasets and open a triage note with the likely upstream cause.',
    model: 'veltrix-reasoning',
    status: 'published',
    tools: ['sql-query', 'semantic-search'],
  },
  {
    id: 'ag_briefing',
    name: 'Morning Briefing',
    goal: 'Assemble a daily KPI briefing from published dashboards and email it to the leadership list.',
    model: 'veltrix-reasoning-pro',
    status: 'published',
    tools: ['dashboard-read', 'report-generator'],
  },
  {
    id: 'ag_triage',
    name: 'Incident Triage',
    goal: 'Investigate quality incidents, gather lineage context and propose a remediation owner.',
    model: 'veltrix-reasoning',
    status: 'draft',
    tools: ['sql-query', 'semantic-search', 'pipeline-trigger'],
  },
]

const AGENT_RUNS: AgentRun[] = [
  {
    id: 'ar_1',
    agent: 'Freshness Sentinel',
    status: 'succeeded',
    startedAt: isoAgo(22),
    durationMs: 18400,
    tokens: 12480,
    cost: 0.19,
    steps: [
      { name: 'Load monitored datasets', status: 'succeeded', tool: 'semantic-search' },
      { name: 'Check freshness SLAs', status: 'succeeded', tool: 'sql-query' },
      { name: 'Correlate upstream pipeline runs', status: 'succeeded', tool: 'sql-query' },
      { name: 'Draft triage note', status: 'succeeded' },
    ],
  },
  {
    id: 'ar_2',
    agent: 'Morning Briefing',
    status: 'running',
    startedAt: isoAgo(2),
    tokens: 8300,
    steps: [
      { name: 'Collect dashboard snapshots', status: 'succeeded', tool: 'dashboard-read' },
      { name: 'Summarize KPI movements', status: 'running' },
      { name: 'Render report', status: 'queued', tool: 'report-generator' },
      { name: 'Queue delivery', status: 'queued' },
    ],
  },
  {
    id: 'ar_3',
    agent: 'Incident Triage',
    status: 'failed',
    startedAt: isoAgo(140),
    durationMs: 9200,
    tokens: 5120,
    cost: 0.08,
    steps: [
      { name: 'Fetch incident context', status: 'succeeded', tool: 'semantic-search' },
      { name: 'Query affected rows', status: 'failed', tool: 'sql-query' },
      { name: 'Propose owner', status: 'queued' },
    ],
  },
  {
    id: 'ar_4',
    agent: 'Freshness Sentinel',
    status: 'queued',
    startedAt: isoAgo(1),
    steps: [
      { name: 'Load monitored datasets', status: 'queued', tool: 'semantic-search' },
      { name: 'Check freshness SLAs', status: 'queued', tool: 'sql-query' },
    ],
  },
]

/** Canned, professional answer streamed word-by-word to simulate an LLM. */
const CANNED_REPLY =
  'Based on the Sales Analytics model, the key driver of the change is a shift in enterprise renewal timing rather than a demand problem. ' +
  'Net revenue is tracking within 3% of plan, and pipeline coverage for the next quarter remains healthy at roughly 3.2x. ' +
  'I would recommend confirming the renewal dates with the RevOps team before treating this as a structural miss. ' +
  'Let me know if you would like this broken down by segment or exported to a report.'

const CANNED_SOURCES: ChatSource[] = [
  { title: 'Sales Analytics — net_revenue', ref: 'semantic:sm_sales/net_revenue' },
  { title: 'fct_revenue_daily', ref: 'dataset:ds_revenue_daily' },
]

export const aiService = {
  async listConversations(): Promise<Conversation[]> {
    await latency()
    return CONVERSATIONS
  },

  async getMessages(convId: string): Promise<ChatMessage[]> {
    await latency()
    return MESSAGES[convId] ?? []
  },

  async listAssistants(): Promise<Assistant[]> {
    await latency()
    return ASSISTANTS
  },

  async listKnowledge(): Promise<KnowledgeBase[]> {
    await latency()
    return KNOWLEDGE
  },

  async listAgents(): Promise<Agent[]> {
    await latency()
    return AGENTS
  },

  async listAgentRuns(): Promise<AgentRun[]> {
    await latency()
    return AGENT_RUNS
  },

  async getAgentRun(id: string): Promise<AgentRun | undefined> {
    await latency()
    return AGENT_RUNS.find((r) => r.id === id)
  },

  /**
   * Simulated streaming reply. Emits words on an interval via `onChunk` and
   * resolves with grounding sources when the stream completes. Pass an
   * `AbortSignal` to support a "Stop generation" control — on abort the stream
   * halts and resolves with whatever sources were gathered so far.
   *
   * INTEGRATION POINT: replace with an SSE/fetch stream reader against
   * POST /api/v1/ai/chat, forwarding decoded tokens to `onChunk`.
   */
  streamReply(
    prompt: string,
    onChunk: (text: string) => void,
    signal?: AbortSignal,
  ): Promise<{ sources: ChatSource[] }> {
    void prompt
    return new Promise((resolve) => {
      const words = CANNED_REPLY.split(' ')
      let i = 0
      const finish = (sources: ChatSource[]): void => {
        clearInterval(timer)
        signal?.removeEventListener('abort', onAbort)
        resolve({ sources })
      }
      const onAbort = (): void => finish([])
      const timer = setInterval(() => {
        if (i >= words.length) {
          finish(CANNED_SOURCES)
          return
        }
        onChunk((i === 0 ? '' : ' ') + words[i])
        i += 1
      }, 45)
      if (signal) {
        if (signal.aborted) onAbort()
        else signal.addEventListener('abort', onAbort)
      }
    })
  },
}
