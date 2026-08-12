<script setup lang="ts">
/**
 * Subtle top-of-viewport progress bar that reflects in-flight data refreshes
 * from the global query-activity stream. Deliberately understated — it only
 * appears when activity persists briefly (so fast requests never flash) and
 * fades out cleanly. Decorative: assistive tech is not spammed per request.
 */
import { ref, watch } from 'vue'
import { useRefreshActivity } from '@/shared/composables/useRefreshActivity'

const { activeRequests } = useRefreshActivity()
const visible = ref(false)
let showTimer: ReturnType<typeof setTimeout> | undefined
let hideTimer: ReturnType<typeof setTimeout> | undefined

watch(activeRequests, (count) => {
  if (count > 0) {
    if (hideTimer) clearTimeout(hideTimer)
    if (!visible.value && !showTimer) {
      // Only surface if the work is slow enough to be worth signalling.
      showTimer = setTimeout(() => {
        visible.value = true
        showTimer = undefined
      }, 220)
    }
  } else {
    if (showTimer) {
      clearTimeout(showTimer)
      showTimer = undefined
    }
    // Let the completion state read as finished before it disappears.
    hideTimer = setTimeout(() => {
      visible.value = false
    }, 360)
  }
})
</script>

<template>
  <div class="vip-refresh-bar" :class="{ 'is-active': visible }" aria-hidden="true">
    <div class="vip-refresh-bar__track"><div class="vip-refresh-bar__glow" /></div>
  </div>
</template>

<style scoped>
.vip-refresh-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  z-index: 1000;
  opacity: 0;
  transition: opacity 220ms ease;
  pointer-events: none;
}
.vip-refresh-bar.is-active {
  opacity: 1;
}
.vip-refresh-bar__track {
  position: relative;
  height: 100%;
  overflow: hidden;
  background: color-mix(in srgb, var(--vip-brand-500) 18%, transparent);
}
.vip-refresh-bar__glow {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  width: 35%;
  background: linear-gradient(
    90deg,
    transparent,
    var(--vip-brand-500),
    color-mix(in srgb, var(--vip-brand-500) 60%, white)
  );
  animation: vip-refresh-slide 1.1s ease-in-out infinite;
}
@keyframes vip-refresh-slide {
  0% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(360%);
  }
}
:global([data-reduced-motion]) .vip-refresh-bar__glow,
:global(html[data-reduced-motion]) .vip-refresh-bar__glow {
  animation: none;
  width: 100%;
  opacity: 0.5;
}
@media (prefers-reduced-motion: reduce) {
  .vip-refresh-bar__glow {
    animation: none;
    width: 100%;
    opacity: 0.5;
  }
}
</style>
