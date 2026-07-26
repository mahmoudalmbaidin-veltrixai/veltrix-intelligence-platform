<script setup lang="ts">
import { useAuthorizationStore } from '@/shared/stores/authorization'

defineProps<{ feature: string }>()
const authorization = useAuthorizationStore()
</script>

<template>
  <slot v-if="authorization.flagEnabled(feature)" />
  <slot v-else name="fallback" />
</template>
