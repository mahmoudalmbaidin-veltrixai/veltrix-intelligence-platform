/** Reactive media-query + named breakpoint helpers for responsive behavior. */
import { ref, onMounted, onBeforeUnmount, type Ref } from 'vue'

export function useMediaQuery(query: string): Ref<boolean> {
  const matches = ref(false)
  let mql: MediaQueryList | undefined
  const update = () => { matches.value = mql?.matches ?? false }

  onMounted(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    mql = window.matchMedia(query)
    update()
    mql.addEventListener('change', update)
  })
  onBeforeUnmount(() => mql?.removeEventListener('change', update))

  return matches
}

/** True below the tablet breakpoint — studios switch to overlay-panel mode. */
export function useIsCompact(): Ref<boolean> {
  return useMediaQuery('(max-width: 899px)')
}

/** True on phone-sized viewports. */
export function useIsMobile(): Ref<boolean> {
  return useMediaQuery('(max-width: 599px)')
}
