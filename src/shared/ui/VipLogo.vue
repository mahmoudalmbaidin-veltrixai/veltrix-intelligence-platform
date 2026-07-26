<script setup lang="ts">
/**
 * Official VIP / Veltrix Intelligence Platform product logo.
 *
 * Single source of truth for the product mark — a transparent, scalable vector
 * reproduction of the official "icon only" Veltrix isometric cube (see
 * Logo/VIP Set.png). Rendered inline so it needs no network request, scales
 * crisply at every size, and works on both light and dark backgrounds.
 *
 * The optional "VIP" wordmark uses currentColor, so it inherits the correct
 * text color per surface/theme automatically.
 */
import { computed, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    /** icon = cube only · full = cube + VIP wordmark · auto = full. */
    variant?: 'icon' | 'full' | 'auto'
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
    /** Explicit mark height in px (overrides size). */
    height?: number
    /** Explicit mark width in px (overrides size; the cube is square). */
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
const labelText = computed(() => props.label ?? 'Veltrix Intelligence Platform')

// Unique gradient ids per instance so multiple logos on one page never collide.
const uid = useId()
const idTop = `vip-top-${uid}`
const idRight = `vip-right-${uid}`
const idLeft = `vip-left-${uid}`
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
      <defs>
        <linearGradient :id="idTop" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#3A97FF" />
          <stop offset="1" stop-color="#1E73E6" />
        </linearGradient>
        <linearGradient :id="idRight" x1="0.2" y1="0" x2="0.8" y2="1">
          <stop offset="0" stop-color="#2C7BE8" />
          <stop offset="1" stop-color="#154FBE" />
        </linearGradient>
        <linearGradient :id="idLeft" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#163C8A" />
          <stop offset="1" stop-color="#0B2258" />
        </linearGradient>
      </defs>
      <path :fill="`url(#${idTop})`" d="M24 4 L41 14 L24 24 L7 14 Z" />
      <path :fill="`url(#${idRight})`" d="M41 14 L41 34 L24 44 L24 24 Z" />
      <path :fill="`url(#${idLeft})`" d="M7 14 L24 24 L24 44 L7 34 Z" />
      <g fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.9">
        <path stroke="#0B2258" stroke-opacity="0.55" d="M15.5 13.8 L24 18.8 L32.5 13.8" />
        <path stroke="#7FB0F0" stroke-opacity="0.6" d="M11.6 20 L11.6 31 L20 36" />
        <path stroke="#A9CCFF" stroke-opacity="0.6" d="M36.4 20 L36.4 31 L28 36" />
      </g>
      <circle cx="24" cy="10" r="1.6" fill="#CFE6FF" />
    </svg>
    <span v-if="showWord" class="vip-logo__word">VIP</span>
  </span>
</template>

<style scoped>
.vip-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.28em;
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
  letter-spacing: 0.06em;
  color: currentColor;
}
.vip-logo--xs .vip-logo__word {
  font-size: 14px;
}
.vip-logo--sm .vip-logo__word {
  font-size: 17px;
}
.vip-logo--md .vip-logo__word {
  font-size: 20px;
}
.vip-logo--lg .vip-logo__word {
  font-size: 26px;
}
.vip-logo--xl .vip-logo__word {
  font-size: 32px;
}
</style>
