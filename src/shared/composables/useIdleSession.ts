/**
 * Client half of the authoritative idle-session timeout. The BACKEND is the
 * source of truth (it revokes idle sessions); this composable provides the UX:
 *
 * - Detects GENUINE user activity (pointer/keyboard/scroll/navigation) and, at
 *   most once per throttle window, tells the server (POST /auth/session/activity)
 *   to renew the sliding idle window. Background polling/SSE never call this, so
 *   they cannot keep a session alive.
 * - Shows a warning modal `warningMinutes` before the idle deadline with a live
 *   countdown; "Stay signed in" performs a real server activity call.
 * - At the deadline it signs the user out and routes to login with a reason.
 * - Synchronises across tabs via BroadcastChannel: activity in one tab renews
 *   the others, and a logout in one tab signs out all of them.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/shared/stores/auth'
import { settingsService } from '@/modules/settings/settings.service'
import { ApiError } from '@/shared/types/api'

const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'scroll', 'touchstart', 'mousemove'] as const
const PING_THROTTLE_MS = 60_000
const DEFAULT_IDLE_MINUTES = 30
const DEFAULT_WARNING_MINUTES = 5
const CHANNEL = 'vip.session'

let started = false

export function useIdleSession() {
  const auth = useAuthStore()
  const router = useRouter()

  const showWarning = ref(false)
  const secondsRemaining = ref(0)
  const idleDeadline = ref(0) // epoch ms
  const warningMs = ref(DEFAULT_WARNING_MINUTES * 60_000)
  let lastPingAt = 0
  let activitySeen = false
  let ticker: ReturnType<typeof setInterval> | undefined
  let channel: BroadcastChannel | undefined
  let loggingOut = false

  function seedFromSession() {
    const session = auth.session
    if (!session) return
    const idleMinutes = session.idleTimeoutMinutes ?? DEFAULT_IDLE_MINUTES
    warningMs.value = (session.warningMinutes ?? DEFAULT_WARNING_MINUTES) * 60_000
    idleDeadline.value = session.idleExpiresAt
      ? new Date(session.idleExpiresAt).getTime()
      : Date.now() + idleMinutes * 60_000
  }

  function onActivity() {
    activitySeen = true
  }

  async function ping(explicit = false): Promise<boolean> {
    try {
      const session = await settingsService.recordActivity()
      lastPingAt = Date.now()
      activitySeen = false
      if (session.idleExpiresAt) {
        idleDeadline.value = new Date(session.idleExpiresAt).getTime()
        channel?.postMessage({ type: 'renew', deadline: idleDeadline.value })
      }
      showWarning.value = false
      return true
    } catch (error) {
      // A 401 means the server already expired/revoked the session.
      if (explicit && error instanceof ApiError && error.kind === 'unauthorized') {
        await forceLogout('idle')
      }
      return false
    }
  }

  async function forceLogout(reason: 'idle', broadcast = true) {
    if (loggingOut) return
    loggingOut = true
    if (broadcast) channel?.postMessage({ type: 'logout', reason })
    showWarning.value = false
    try {
      await auth.logout()
    } finally {
      await router.replace({ name: 'login', query: { reason } })
      loggingOut = false
    }
  }

  async function staySignedIn() {
    const ok = await ping(true)
    if (ok) showWarning.value = false
  }

  function signOutNow() {
    void forceLogout('idle')
  }

  function tick() {
    if (!auth.isAuthenticated || idleDeadline.value === 0) {
      showWarning.value = false
      return
    }
    const now = Date.now()
    if (now >= idleDeadline.value) {
      void forceLogout('idle')
      return
    }
    if (now >= idleDeadline.value - warningMs.value) {
      // In the warning window: do NOT auto-extend; require an explicit choice.
      showWarning.value = true
      secondsRemaining.value = Math.max(0, Math.ceil((idleDeadline.value - now) / 1000))
      return
    }
    showWarning.value = false
    // Before the warning: renew on genuine, throttled activity.
    if (activitySeen && now - lastPingAt >= PING_THROTTLE_MS) {
      void ping(false)
    }
  }

  function start() {
    if (started) return
    started = true
    seedFromSession()
    lastPingAt = Date.now()
    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, onActivity, { passive: true })
    }
    if ('BroadcastChannel' in window) {
      channel = new BroadcastChannel(CHANNEL)
      channel.onmessage = (message: MessageEvent) => {
        const data = message.data as { type?: string; deadline?: number; reason?: 'idle' }
        if (data?.type === 'renew' && typeof data.deadline === 'number') {
          idleDeadline.value = data.deadline
          showWarning.value = false
        } else if (data?.type === 'logout') {
          void forceLogout('idle', false)
        }
      }
    }
    ticker = setInterval(tick, 1000)
  }

  function stop() {
    started = false
    if (ticker) clearInterval(ticker)
    for (const event of ACTIVITY_EVENTS) window.removeEventListener(event, onActivity)
    channel?.close()
    channel = undefined
    showWarning.value = false
    idleDeadline.value = 0
  }

  // Activate only while authenticated; re-seed whenever the session changes.
  watch(
    () => auth.isAuthenticated,
    (isAuth) => {
      if (isAuth) start()
      else stop()
    },
    { immediate: true },
  )
  watch(
    () => auth.session?.idleExpiresAt,
    () => seedFromSession(),
  )

  onBeforeUnmount(stop)

  return {
    showWarning,
    secondsRemaining,
    countdownLabel: computed(() => {
      const total = secondsRemaining.value
      const m = Math.floor(total / 60)
      const s = total % 60
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    }),
    staySignedIn,
    signOutNow,
  }
}
