<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUiStore } from '@/shared/stores/ui'
import { usePlatformStore } from '@/shared/stores/platform'
import { NAV_GROUPS, QUICK_CREATE, type NavItem } from '@/app/navigation'
import { SEARCH_PROVIDERS, type SearchResult } from './providers'
import VipIcon from '@/shared/ui/VipIcon.vue'

const ui = useUiStore()
const platform = usePlatformStore()
const router = useRouter()

const query = ref('')
const activeIndex = ref(0)
const inputEl = ref<HTMLInputElement>()

interface Cmd {
  id: string
  title: string
  subtitle?: string
  icon: string
  group: string
  run: () => void
}

function allowed(item: NavItem): boolean {
  if (item.permission && !platform.can(item.permission)) return false
  if (item.entitlement && !platform.entitled(item.entitlement)) return false
  if (item.featureFlag && !platform.flagEnabled(item.featureFlag)) return false
  return true
}

const navCommands = computed<Cmd[]>(() =>
  NAV_GROUPS.flatMap((g) =>
    g.items.filter(allowed).map((i) => ({
      id: `nav-${i.to}`,
      title: i.label,
      subtitle: `Go to ${g.label}`,
      icon: i.icon,
      group: 'Navigate',
      run: () => router.push(i.to),
    })),
  ),
)
const createCommands = computed<Cmd[]>(() =>
  QUICK_CREATE.filter(allowed).map((i) => ({
    id: `create-${i.to}`,
    title: i.label,
    subtitle: 'Quick create',
    icon: i.icon,
    group: 'Create',
    run: () => router.push(i.to),
  })),
)
const actionCommands = computed<Cmd[]>(() => [
  { id: 'act-ai', title: 'Open AI Assistant', icon: 'bot', group: 'Actions', run: () => router.push('/ai/assistant') },
  {
    id: 'act-theme',
    title: 'Toggle theme',
    icon: 'moon',
    group: 'Actions',
    run: () => import('@/shared/stores/theme').then((m) => m.useThemeStore().cycle()),
  },
])

const searchResults = computed<Cmd[]>(() => {
  if (query.value.trim().length < 1) return []
  return SEARCH_PROVIDERS.flatMap((p) => p.search(query.value)).map((r: SearchResult) => ({
    id: r.id,
    title: r.title,
    subtitle: r.subtitle,
    icon: r.icon,
    group: r.group,
    run: () => router.push(r.to),
  }))
})

const results = computed<Cmd[]>(() => {
  const q = query.value.trim().toLowerCase()
  const base = [...createCommands.value, ...navCommands.value, ...actionCommands.value]
  const filtered = q
    ? base.filter((c) => c.title.toLowerCase().includes(q) || c.subtitle?.toLowerCase().includes(q))
    : base
  return [...searchResults.value, ...filtered].slice(0, 40)
})

const grouped = computed(() => {
  const map = new Map<string, Cmd[]>()
  results.value.forEach((c) => {
    if (!map.has(c.group)) map.set(c.group, [])
    map.get(c.group)!.push(c)
  })
  return [...map.entries()]
})

function flatIndexOf(cmd: Cmd): number {
  return results.value.findIndex((c) => c.id === cmd.id)
}

function run(cmd: Cmd) {
  cmd.run()
  ui.closeCommand()
}
function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (ui.commandOpen) ui.closeCommand()
    else ui.openCommand()
    return
  }
  if (!ui.commandOpen) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(results.value.length - 1, activeIndex.value + 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const c = results.value[activeIndex.value]
    if (c) run(c)
  } else if (e.key === 'Escape') {
    ui.closeCommand()
  }
}

watch(
  () => ui.commandOpen,
  async (open) => {
    if (open) {
      query.value = ''
      activeIndex.value = 0
      await nextTick()
      inputEl.value?.focus()
    }
  },
)
watch(query, () => (activeIndex.value = 0))

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <Transition name="vip-cmd">
      <div v-if="ui.commandOpen" class="vip-cmd__scrim" @click.self="ui.closeCommand()">
        <div class="vip-cmd" role="dialog" aria-modal="true" aria-label="Command palette">
          <div class="vip-cmd__search">
            <VipIcon name="search" :size="17" />
            <input
              ref="inputEl"
              v-model="query"
              class="vip-cmd__input"
              placeholder="Search resources, run commands, navigate…"
              aria-label="Command search"
            />
            <kbd class="vip-cmd__esc">ESC</kbd>
          </div>
          <div class="vip-cmd__results">
            <div v-if="!results.length" class="vip-cmd__empty">No matches for “{{ query }}”.</div>
            <div v-for="[group, cmds] in grouped" :key="group" class="vip-cmd__group">
              <div class="vip-cmd__group-label">{{ group }}</div>
              <button
                v-for="cmd in cmds"
                :key="cmd.id"
                type="button"
                class="vip-cmd__item"
                :class="{ 'is-active': flatIndexOf(cmd) === activeIndex }"
                @mousemove="activeIndex = flatIndexOf(cmd)"
                @click="run(cmd)"
              >
                <VipIcon :name="cmd.icon" :size="16" />
                <span class="vip-cmd__title">{{ cmd.title }}</span>
                <span v-if="cmd.subtitle" class="vip-cmd__sub">{{ cmd.subtitle }}</span>
              </button>
            </div>
          </div>
          <footer class="vip-cmd__footer">
            <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
            <span><kbd>↵</kbd> select</span>
            <span><kbd>⌘K</kbd> toggle</span>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.vip-cmd__scrim {
  position: fixed;
  inset: 0;
  z-index: var(--vip-z-popover);
  background: var(--vip-scrim);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 12vh var(--vip-sp-6) var(--vip-sp-6);
}
.vip-cmd {
  width: 100%;
  max-width: 620px;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-xl);
  box-shadow: var(--vip-shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 66vh;
}
.vip-cmd__search {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-6);
  border-bottom: 1px solid var(--vip-border-subtle);
  color: var(--vip-text-muted);
}
.vip-cmd__input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-lg);
}
.vip-cmd__esc {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-muted);
  background: var(--vip-surface-3);
  padding: 2px 6px;
  border-radius: var(--vip-radius-xs);
}
.vip-cmd__results {
  overflow-y: auto;
  padding: var(--vip-sp-4);
}
.vip-cmd__empty {
  padding: var(--vip-sp-8);
  text-align: center;
  color: var(--vip-text-muted);
}
.vip-cmd__group {
  margin-bottom: var(--vip-sp-4);
}
.vip-cmd__group-label {
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: var(--vip-ls-wide);
  color: var(--vip-text-disabled);
  padding: var(--vip-sp-3) var(--vip-sp-4);
}
.vip-cmd__item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  width: 100%;
  padding: var(--vip-sp-4);
  border: none;
  background: none;
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  text-align: left;
}
.vip-cmd__item.is-active {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.vip-cmd__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
}
.vip-cmd__sub {
  margin-left: auto;
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.vip-cmd__footer {
  display: flex;
  gap: var(--vip-sp-7);
  padding: var(--vip-sp-4) var(--vip-sp-6);
  border-top: 1px solid var(--vip-border-subtle);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.vip-cmd__footer kbd {
  font-family: var(--vip-font-mono);
  background: var(--vip-surface-3);
  padding: 1px 5px;
  border-radius: var(--vip-radius-xs);
  margin-right: 2px;
}
.vip-cmd-enter-active,
.vip-cmd-leave-active {
  transition: opacity var(--vip-motion-fast);
}
.vip-cmd-enter-active .vip-cmd {
  transition: transform var(--vip-motion-base) var(--vip-ease-emphasized);
}
.vip-cmd-enter-from {
  opacity: 0;
}
.vip-cmd-enter-from .vip-cmd {
  transform: translateY(-14px);
}
</style>
