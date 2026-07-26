<script setup lang="ts">
import { useAuthorizationStore } from '@/shared/stores/authorization'

defineProps<{ entitlement: string }>()
const authorization = useAuthorizationStore()
</script>

<template>
  <slot v-if="authorization.entitled(entitlement)" />
  <slot v-else name="fallback" />
</template>
