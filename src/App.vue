<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/app/layouts/AppLayout.vue'
import StudioLayout from '@/app/layouts/StudioLayout.vue'
import SettingsLayout from '@/app/layouts/SettingsLayout.vue'
import BlankLayout from '@/app/layouts/BlankLayout.vue'
import ToastHost from '@/shared/ui/ToastHost.vue'
import CommandPalette from '@/shared/ui/command/CommandPalette.vue'

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
</script>

<template>
  <a href="#vip-main" class="vip-skip-link">Skip to main content</a>
  <component :is="layout" />
  <ToastHost />
  <CommandPalette />
</template>
