<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { invalidateQueries } from '@/shared/lib/query'
import { platformInfrastructure } from '@/shared/services/platformInfrastructure'
import AppSidebar from '@/app/shell/AppSidebar.vue'
import AppTopbar from '@/app/shell/AppTopbar.vue'
import MobileNav from '@/app/shell/MobileNav.vue'
import NotificationDrawer from '@/app/shell/NotificationDrawer.vue'

const route = useRoute()
const platform = usePlatformStore()
const ui = useUiStore()
const fullBleed = computed(() => route.meta.fullBleed === true)
let eventsController: AbortController | undefined

watch(
  () => [platform.organization?.id, platform.workspace?.id, platform.can('events.subscribe')] as const,
  ([organizationId, workspaceId, allowed]) => {
    eventsController?.abort()
    eventsController = undefined
    if (!organizationId || !workspaceId || !allowed) return
    eventsController = new AbortController()
    const signal = eventsController.signal
    void (async () => {
      try {
        for await (const event of platformInfrastructure.resilientEvents([], {
          scope: `${organizationId}:${workspaceId}`,
          signal,
        })) {
          if (event.type === 'stream.replay_gap') {
            invalidateQueries('')
            ui.pushToast({
              kind: 'warning',
              title: 'Live updates resynchronized',
              message: 'Some older events expired, so the current workspace data was refreshed.',
            })
            continue
          }
          invalidateQueries('home:')
          if (event.type.startsWith('job.')) invalidateQueries('jobs')
          if (event.type.startsWith('file.')) invalidateQueries('files')
          if (event.type.includes('export')) invalidateQueries('dashboard')
          if (event.type.endsWith('.failed')) {
            ui.unreadNotifications += 1
            ui.pushToast({ kind: 'error', title: 'Background operation failed' })
          }
        }
      } catch {
        if (!signal.aborted) {
          ui.pushToast({
            kind: 'warning',
            title: 'Live updates unavailable',
            message: 'Refresh the page after verifying your connection and permissions.',
          })
        }
      }
    })()
  },
  { immediate: true },
)
onBeforeUnmount(() => eventsController?.abort())
</script>

<template>
  <div class="vip-app">
    <AppSidebar class="vip-app__sidebar" />
    <div class="vip-app__col">
      <AppTopbar />
      <main id="vip-main" class="vip-app__main" :class="{ 'is-full-bleed': fullBleed }">
        <RouterView v-slot="{ Component }">
          <Transition name="vip-fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
    <MobileNav />
    <NotificationDrawer />
  </div>
</template>

<style scoped>
.vip-app {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--vip-bg-app);
}
.vip-app__sidebar {
  flex: none;
}
.vip-app__col {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.vip-app__main {
  flex: 1;
  overflow-y: auto;
  padding: var(--vip-sp-8) var(--vip-sp-9);
}
.vip-app__main.is-full-bleed {
  padding: 0;
  overflow: hidden;
  display: flex;
}
@media (max-width: 768px) {
  .vip-app__sidebar {
    display: none;
  }
  .vip-app__main {
    padding: var(--vip-sp-6);
  }
}
</style>
