<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { accessService } from './access.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { safeErrorText } from '@/shared/lib/safeError'
import { useUiStore } from '@/shared/stores/ui'
import VipButton from '@/shared/ui/VipButton.vue'
import ResourceShareDialog from './ResourceShareDialog.vue'

/**
 * Reusable "Share" action for any resource studio/detail view. Encapsulates the
 * level-ladder lookup, the manage-permission check and the shared
 * {@link ResourceShareDialog}. Backend enforcement is authoritative — this button
 * is a convenience entry point only, so a user without `resource.permissions.manage`
 * still sees the dialog in read-only mode (grant/revoke controls are hidden).
 */
const props = withDefaults(
  defineProps<{
    resourceType: string
    resourceId: string
    resourceName?: string
    disabled?: boolean
    variant?: 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger'
    size?: 'xs' | 'sm' | 'md' | 'lg'
    label?: string
  }>(),
  { variant: 'secondary', size: 'md', label: 'Share' },
)

const platform = usePlatformStore()
const ui = useUiStore()
const open = ref(false)
const levels = ref<string[]>([])

const canManage = computed(() => platform.can('resource.permissions.manage'))
const isDisabled = computed(() => props.disabled || !props.resourceId || props.resourceId === 'new')

onMounted(async () => {
  try {
    const types = await accessService.listResourceTypes()
    levels.value = types.find((t) => t.resource_type === props.resourceType)?.levels ?? []
  } catch (e) {
    // Non-fatal: the dialog still opens; the grant selector will simply be empty.
    ui.pushToast({ kind: 'error', title: 'Could not load access levels', message: safeErrorText(e) })
  }
})
</script>

<template>
  <VipButton
    :variant="variant"
    :size="size"
    icon="share"
    :disabled="isDisabled"
    :title="isDisabled ? 'Save the resource before sharing' : 'Manage access'"
    @click="open = true"
  >
    {{ label }}
  </VipButton>
  <ResourceShareDialog
    :open="open"
    :resource-type="resourceType"
    :resource-id="resourceId"
    :resource-name="resourceName || undefined"
    :levels="levels"
    :can-manage="canManage"
    @close="open = false"
  />
</template>
