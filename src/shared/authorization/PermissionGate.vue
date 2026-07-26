<script setup lang="ts">
import { useAuthorizationStore } from '@/shared/stores/authorization'

defineProps<{ permission: string }>()
const authorization = useAuthorizationStore()
</script>

<template>
  <slot v-if="authorization.can(permission)" />
  <slot v-else name="fallback" />
</template>
