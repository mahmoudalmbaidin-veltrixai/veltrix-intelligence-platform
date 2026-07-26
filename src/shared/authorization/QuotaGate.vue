<script setup lang="ts">
import { useAuthorizationStore } from '@/shared/stores/authorization'

withDefaults(defineProps<{ quota: string; amount?: number }>(), { amount: 1 })
const authorization = useAuthorizationStore()
</script>

<template>
  <slot v-if="authorization.quotaAvailable(quota, amount)" />
  <slot v-else name="fallback" />
</template>
