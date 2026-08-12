/**
 * Reactive view of the global query-activity stream that `query.ts` already
 * publishes (a `vip:query-activity` window event plus `window.__vipQueryActivity`).
 * Lets a single subtle global indicator reflect in-flight refreshes without
 * coupling every fetch to a blocking popup.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

interface QueryActivityDetail {
  active: number
}

export function useRefreshActivity() {
  const activeRequests = ref(0)

  function onActivity(event: Event) {
    const detail = (event as CustomEvent<QueryActivityDetail>).detail
    activeRequests.value = Math.max(0, detail?.active ?? 0)
  }

  onMounted(() => {
    if (typeof window === 'undefined') return
    const current = (window as unknown as { __vipQueryActivity?: number }).__vipQueryActivity
    if (typeof current === 'number') activeRequests.value = Math.max(0, current)
    window.addEventListener('vip:query-activity', onActivity)
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') return
    window.removeEventListener('vip:query-activity', onActivity)
  })

  return { activeRequests }
}
