/**
 * Global screen-reader announcer. A single polite/assertive live region is
 * mounted once (AriaLive.vue); anywhere in the app can call `announce()` to
 * queue a message — used for route changes, async results, toasts and
 * canvas selection changes.
 */
import { ref } from 'vue'

const politeMessage = ref('')
const assertiveMessage = ref('')

export function announce(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
  const target = priority === 'assertive' ? assertiveMessage : politeMessage
  // Clear then set so repeated identical messages are re-announced.
  target.value = ''
  requestAnimationFrame(() => {
    target.value = message
  })
}

export function useAnnouncerState() {
  return { politeMessage, assertiveMessage }
}
