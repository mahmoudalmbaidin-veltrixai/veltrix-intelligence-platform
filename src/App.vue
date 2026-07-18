<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/app/layouts/AppLayout.vue'
import StudioLayout from '@/app/layouts/StudioLayout.vue'
import SettingsLayout from '@/app/layouts/SettingsLayout.vue'
import BlankLayout from '@/app/layouts/BlankLayout.vue'
import ToastHost from '@/shared/ui/ToastHost.vue'
import CommandPalette from '@/shared/ui/command/CommandPalette.vue'
import AriaLive from '@/shared/ui/AriaLive.vue'
import { announce } from '@/shared/composables/useAnnouncer'

const route = useRoute()
const layout = computed(() => {
  switch (route.meta.layout) {
    case 'studio':
      return StudioLayout
    case 'settings':
      return SettingsLayout
    case 'error':
    case 'auth':
    case 'blank':
      return BlankLayout
    default:
      return AppLayout
  }
})

// Announce navigation to screen readers (route titles are not read by default).
watch(
  () => route.meta.title,
  (title) => {
    if (title) announce(`${title} page loaded`)
  },
)
</script>

<template>
  <a href="#vip-main" class="vip-skip-link">Skip to main content</a>
  <component :is="layout" />
  <ToastHost />
  <CommandPalette />
  <AriaLive />
</template>
