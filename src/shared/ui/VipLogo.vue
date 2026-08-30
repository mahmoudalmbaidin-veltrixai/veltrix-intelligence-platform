<script setup lang="ts">
/**
 * Official Veltrix One product logo.
 *
 * Single source of truth for the product mark — a flat, self-contained brand
 * badge (rounded square + "V" chevron + a unifying node) rendered inline so it
 * needs no network request, scales crisply at every size, and reads clearly on
 * both light and dark surfaces. The mark uses explicit brand colors (not
 * currentColor) so it stays on-brand even where surrounding SVG color is forced.
 *
 * The optional "Veltrix One" wordmark uses currentColor, so it inherits the
 * correct text color per surface/theme automatically.
 *
 * (Internal component name remains VipLogo to avoid churn across the codebase;
 * only the visible identity is Veltrix One.)
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** icon = badge only · full = badge + "Veltrix One" wordmark · auto = full. */
    variant?: 'icon' | 'full' | 'auto'
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
    /** Explicit mark height in px (overrides size). */
    height?: number
    /** Explicit mark width in px (overrides size; the mark is square). */
    width?: number
    /** Accessible name when the logo conveys product identity. */
    label?: string
    /** Decorative mode — hidden from assistive tech (use when adjacent text names the product). */
    decorative?: boolean
  }>(),
  { variant: 'full', size: 'md' },
)

const MARK_PX: Record<NonNullable<typeof props.size>, number> = {
  xs: 20,
  sm: 28,
  md: 34,
  lg: 44,
  xl: 56,
}

// The mark is intrinsically square; height wins, then width, then the size token.
const markSize = computed(() => props.height ?? props.width ?? MARK_PX[props.size])
const showWord = computed(() => props.variant !== 'icon')
const labelText = computed(() => props.label ?? 'Veltrix One')
</script>

<template>
  <span
    class="vip-logo"
    :class="`vip-logo--${size}`"
    :role="decorative ? undefined : 'img'"
    :aria-label="decorative ? undefined : labelText"
    :aria-hidden="decorative ? 'true' : undefined"
  >
    <svg
      class="vip-logo__mark"
      :width="markSize"
      :height="markSize"
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
      draggable="false"
    >
      <rect x="3" y="3" width="42" height="42" rx="11" fill="#1E73E6" />
      <path
        d="M14 15.5 L24 32.5 L34 15.5"
        fill="none"
        stroke="#ffffff"
        stroke-width="4.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <circle cx="24" cy="12.5" r="2.6" fill="#ffffff" />
    </svg>
    <span v-if="showWord" class="vip-logo__word">Veltrix One</span>
  </span>
</template>

<style scoped>
.vip-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.42em;
  line-height: 1;
  user-select: none;
}
.vip-logo__mark {
  display: block;
  flex: none;
  object-fit: contain;
  -webkit-user-drag: none;
}
.vip-logo__word {
  font-weight: var(--vip-fw-bold);
  letter-spacing: -0.01em;
  white-space: nowrap;
  color: currentColor;
}
.vip-logo--xs .vip-logo__word {
  font-size: 14px;
}
.vip-logo--sm .vip-logo__word {
  font-size: 16px;
}
.vip-logo--md .vip-logo__word {
  font-size: 19px;
}
.vip-logo--lg .vip-logo__word {
  font-size: 23px;
}
.vip-logo--xl .vip-logo__word {
  font-size: 28px;
}
</style>
