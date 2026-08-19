<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { isNavigationFailure, useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/shared/stores/auth'
import { LocalStore } from '@/shared/lib/mock'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const idleExpired = computed(() => route.query.reason === 'idle')
const expired = computed(() => route.query.expired === '1' && !idleExpired.value)

// Remember-me persists ONLY the email address — never the password.
const rememberStore = new LocalStore<{ email: string }>('vip.auth.rememberedEmail')
const rememberedEmail = rememberStore.read({ email: '' }).email

const email = ref(rememberedEmail)
const password = ref('')
const remember = ref(!!rememberedEmail)
const showPassword = ref(false)
const capsOn = ref(false)
const submitting = ref(false)
const attempted = ref(false)
const shake = ref(false)
const navigationError = ref('')

const passwordField = ref<InstanceType<typeof VipInput>>()

// Brand-panel ecosystem (presentational only — no auth behavior).
const ecosystem: { icon: string; label: string }[] = [
  { icon: 'plug', label: 'Connection Studio' },
  { icon: 'workflow', label: 'Pipeline Studio' },
  { icon: 'database', label: 'Dataset & Semantic layer' },
  { icon: 'chart', label: 'Dashboard Studio' },
  { icon: 'shield', label: 'Governance & Security' },
]

// Client-side validation surfaces only after the first submit attempt (live thereafter).
// The identifier may be a username or an email, so only require a non-empty value.
const emailClientError = computed(() => {
  if (!attempted.value) return ''
  if (!email.value.trim()) return 'Enter your username or email.'
  return ''
})
const passwordClientError = computed(() => {
  if (!attempted.value) return ''
  if (!password.value) return 'Enter your password.'
  return ''
})

const serverFieldError = (field: string) => auth.error?.fieldErrors?.find((f) => f.field === field)?.message
const emailError = computed(() => emailClientError.value || serverFieldError('email'))
const passwordError = computed(() => passwordClientError.value || serverFieldError('password'))
const generalError = computed(() => {
  if (navigationError.value) return navigationError.value
  if (!auth.error || auth.error.fieldErrors?.length) return ''
  return auth.error.kind === 'unauthorized' ? 'Invalid email or password.' : auth.error.friendlyMessage
})

function onPwKey(e: KeyboardEvent) {
  if (typeof e.getModifierState === 'function') capsOn.value = e.getModifierState('CapsLock')
}

function pwEl(): HTMLInputElement | undefined {
  // defineExpose unwraps the ref at runtime; the TS type still shows a Ref.
  return passwordField.value?.el as unknown as HTMLInputElement | undefined
}

async function togglePassword() {
  const caret = pwEl()?.selectionStart ?? null
  showPassword.value = !showPassword.value
  // Restore focus and caret so toggling does not disrupt typing.
  await nextTick()
  passwordField.value?.focus()
  const el = pwEl()
  if (el && caret != null) {
    try {
      el.setSelectionRange(caret, caret)
    } catch {
      /* some input types disallow setSelectionRange — safe to ignore */
    }
  }
}

function triggerShake() {
  shake.value = false
  // Force reflow so the animation restarts on repeated failures.
  requestAnimationFrame(() => (shake.value = true))
  setTimeout(() => (shake.value = false), 500)
}

async function submit() {
  if (submitting.value) return // prevent double-submit
  attempted.value = true
  if (!email.value.trim() || !password.value) {
    triggerShake()
    return
  }
  submitting.value = true
  navigationError.value = ''
  const ok = await auth.login(email.value.trim(), password.value)
  if (ok) {
    if (remember.value) rememberStore.write({ email: email.value.trim() })
    else rememberStore.clear()
    try {
      const failure = await router.replace(auth.takeIntended())
      if (isNavigationFailure(failure)) throw failure
    } catch {
      navigationError.value = 'Your session is ready, but the application could not open. Refresh to continue safely.'
      triggerShake()
    }
  } else {
    triggerShake()
  }
  submitting.value = false
}
</script>

<template>
  <div class="login">
    <!-- Brand experience panel — establishes enterprise credibility; hidden on small screens. -->
    <aside class="login__aside" aria-hidden="true">
      <div class="login__aside-grid"></div>
      <div class="login__aside-inner">
        <VipLogo variant="full" size="lg" decorative />
        <h2 class="login__aside-title">
          One enterprise platform for connected data, governed analytics and dashboards.
        </h2>
        <p class="login__aside-lede">
          Veltrix unifies connections, pipelines, governed semantics and dashboards behind role-based control — so teams
          move from raw data to trusted decisions on a single, secure foundation.
        </p>
        <ul class="login__eco">
          <li v-for="cap in ecosystem" :key="cap.label" class="login__eco-item">
            <span class="login__eco-icon"><VipIcon :name="cap.icon" :size="16" /></span>
            <span>{{ cap.label }}</span>
          </li>
        </ul>
        <div class="login__trust">
          <span class="login__trust-item"><VipIcon name="shield" :size="14" /> Governed access</span>
          <span class="login__trust-item"><VipIcon name="lock" :size="14" /> Encrypted secrets</span>
          <span class="login__trust-item"><VipIcon name="layers" :size="14" /> Multi-tenant</span>
        </div>
      </div>
    </aside>

    <!-- Authentication panel -->
    <div class="login__panel">
      <div class="login__card" :class="{ 'is-shake': shake }">
        <div class="login__brand">
          <VipLogo variant="full" size="lg" decorative />
        </div>
        <h1 class="login__title">Sign in to Veltrix Intelligence</h1>
        <p class="login__sub">Access your Veltrix Intelligence Platform workspace.</p>

        <VipAlert v-if="idleExpired" tone="warning" title="Session expired"
          >You were signed out after 30 minutes of inactivity for security.</VipAlert
        >
        <VipAlert v-else-if="expired" tone="warning" title="Session expired"
          >Your session ended. Please sign in again to continue.</VipAlert
        >
        <VipAlert v-if="generalError" tone="danger" title="Sign-in failed">{{ generalError }}</VipAlert>

        <form class="login__form" novalidate @submit.prevent="submit">
          <VipInput
            v-model="email"
            label="Username or email"
            type="text"
            name="username"
            autocomplete="username"
            icon="users"
            placeholder="your.username"
            :error="emailError"
            :disabled="submitting"
            required
          />

          <div class="login__pw">
            <VipInput
              ref="passwordField"
              v-model="password"
              label="Password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              autocomplete="current-password"
              icon="lock"
              placeholder="Enter your password"
              :error="passwordError"
              :disabled="submitting"
              required
              @keydown="onPwKey"
              @keyup="onPwKey"
            >
              <template #suffix>
                <button
                  type="button"
                  class="login__eye"
                  :aria-label="showPassword ? 'Hide password' : 'Show password'"
                  :aria-pressed="showPassword"
                  :disabled="submitting"
                  tabindex="0"
                  @click="togglePassword"
                >
                  <VipIcon :name="showPassword ? 'eyeOff' : 'eye'" :size="16" />
                </button>
              </template>
            </VipInput>
            <p v-if="capsOn" class="login__caps" role="status"><VipIcon name="warning" :size="13" /> Caps Lock is ON</p>
          </div>

          <div class="login__row">
            <label class="login__remember">
              <input v-model="remember" type="checkbox" class="login__check" :disabled="submitting" />
              <span>Remember me</span>
            </label>
            <RouterLink class="login__forgot" to="/forgot-password">Forgot password?</RouterLink>
          </div>

          <VipButton type="submit" variant="primary" size="lg" block :loading="submitting" :disabled="submitting">
            {{ submitting ? 'Signing in…' : 'Sign in' }}
          </VipButton>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login {
  /* Full-bleed: the shared blank layout centers a 560px column; the login owns
     the whole viewport for its two-panel experience without altering that layout. */
  position: fixed;
  inset: 0;
  overflow-y: auto;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: var(--vip-bg-app);
}

/* ---- Brand experience panel (left) ---- */
.login__aside {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  padding: var(--vip-sp-9);
  color: #eaf0fb;
  /* Deliberate deep, brand-tinted enterprise surface (pre-auth brand identity). */
  background:
    radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, var(--vip-brand-500) 42%, transparent), transparent 60%),
    linear-gradient(160deg, #0b1220 0%, #111c30 55%, #0d1728 100%);
}
/* Restrained data-grid motif — no glow, low contrast. */
.login__aside-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(color-mix(in srgb, #ffffff 6%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, #ffffff 6%, transparent) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(circle at 30% 40%, #000 0%, transparent 72%);
  pointer-events: none;
}
.login__aside-inner {
  position: relative;
  max-width: 460px;
  margin-inline: auto;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.login__aside-inner :deep(svg),
.login__aside-inner :deep(.vip-logo) {
  color: #fff;
}
.login__aside-title {
  font-size: var(--vip-fs-2xl);
  font-weight: var(--vip-fw-semibold);
  line-height: 1.25;
  letter-spacing: -0.01em;
  max-width: 22ch;
}
.login__aside-lede {
  font-size: var(--vip-fs-md);
  line-height: 1.6;
  color: color-mix(in srgb, #eaf0fb 78%, transparent);
}
.login__eco {
  list-style: none;
  margin: var(--vip-sp-2) 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-3) var(--vip-sp-5);
}
.login__eco-item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: color-mix(in srgb, #eaf0fb 90%, transparent);
}
.login__eco-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: var(--vip-radius-md);
  background: color-mix(in srgb, var(--vip-brand-400) 22%, transparent);
  border: 1px solid color-mix(in srgb, #ffffff 12%, transparent);
  color: #dbe6ff;
}
.login__trust {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3) var(--vip-sp-5);
  margin-top: var(--vip-sp-4);
  padding-top: var(--vip-sp-5);
  border-top: 1px solid color-mix(in srgb, #ffffff 12%, transparent);
}
.login__trust-item {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-xs);
  font-weight: var(--vip-fw-medium);
  color: color-mix(in srgb, #eaf0fb 72%, transparent);
}

/* ---- Authentication panel (right) ---- */
.login__panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--vip-sp-8);
}
.login__card {
  width: 100%;
  max-width: 408px;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-xl);
  padding: var(--vip-sp-9);
  box-shadow: var(--vip-shadow-lg);
}
.login__card.is-shake {
  animation: login-shake 0.42s var(--vip-ease-standard);
}
.login__brand {
  display: flex;
  align-items: center;
  margin-bottom: var(--vip-sp-7);
  color: var(--vip-text-primary);
}
.login__title {
  font-size: var(--vip-fs-2xl);
  font-weight: var(--vip-fw-semibold);
  letter-spacing: -0.01em;
  line-height: 1.2;
}
.login__sub {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-md);
  margin: var(--vip-sp-3) 0 var(--vip-sp-7);
}
.login__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.login__pw {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.login__eye {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  margin-right: calc(var(--vip-sp-2) * -1);
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
  flex: none;
  transition:
    color var(--vip-motion-fast),
    background var(--vip-motion-fast);
}
.login__eye:hover:not(:disabled) {
  color: var(--vip-text-primary);
  background: var(--vip-surface-hover);
}
.login__eye:disabled {
  opacity: 0.5;
}
.login__caps {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-xs);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-warning-text);
}
.login__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  margin-top: calc(var(--vip-sp-2) * -1);
}
.login__remember {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  cursor: pointer;
  user-select: none;
}
.login__check {
  width: 16px;
  height: 16px;
  accent-color: var(--vip-brand-500);
  cursor: pointer;
}
.login__forgot {
  background: none;
  border: none;
  padding: 0;
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-brand-text);
  cursor: pointer;
  border-radius: var(--vip-radius-xs);
}
.login__forgot:hover:not(:disabled) {
  text-decoration: underline;
}
.login__forgot:disabled {
  opacity: 0.5;
  cursor: default;
}
.login__note {
  margin-top: var(--vip-sp-7);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  text-align: center;
}
.login__note code {
  font-family: var(--vip-font-mono);
  background: var(--vip-surface-3);
  padding: 1px 5px;
  border-radius: var(--vip-radius-xs);
}

/* Collapse to a single, auth-focused column; drop the brand panel. */
@media (max-width: 960px) {
  .login {
    grid-template-columns: 1fr;
  }
  .login__aside {
    display: none;
  }
}

@media (max-width: 480px) {
  .login__panel {
    align-items: flex-start;
    padding: var(--vip-sp-4);
  }
  .login__card {
    padding: var(--vip-sp-6);
  }
  .login__brand {
    margin-bottom: var(--vip-sp-6);
  }
  .login__row {
    gap: var(--vip-sp-3);
  }
}

@keyframes login-shake {
  10%,
  90% {
    transform: translateX(-2px);
  }
  20%,
  80% {
    transform: translateX(4px);
  }
  30%,
  50%,
  70% {
    transform: translateX(-7px);
  }
  40%,
  60% {
    transform: translateX(7px);
  }
}
</style>
