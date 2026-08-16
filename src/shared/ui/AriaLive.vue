<script setup lang="ts">
import { useAnnouncerState } from '@/shared/composables/useAnnouncer'
const { politeMessage, assertiveMessage } = useAnnouncerState()
</script>

<template>
  <div class="vip-visually-hidden">
    <div role="status" aria-live="polite" aria-atomic="true">{{ politeMessage }}</div>
    <div role="alert" aria-live="assertive" aria-atomic="true">{{ assertiveMessage }}</div>
  </div>
</template>
