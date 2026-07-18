<script setup lang="ts">
import { useAnnouncerState } from '@/shared/composables/useAnnouncer'
const { politeMessage, assertiveMessage } = useAnnouncerState()
</script>

<template>
  <div class="vip-visually-hidden">
    <div aria-live="polite" aria-atomic="true">{{ politeMessage }}</div>
    <div aria-live="assertive" aria-atomic="true" role="alert">{{ assertiveMessage }}</div>
  </div>
</template>
