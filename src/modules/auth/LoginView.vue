<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
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
const expired = computed(() => route.query.expired === '1')

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

const passwordField = ref<InstanceType<typeof VipInput>>()

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
  const ok = await auth.login(email.value.trim(), password.value)
  submitting.value = false
  if (ok) {
    if (remember.value) rememberStore.write({ email: email.value.trim() })
    else rememberStore.clear()
    router.replace(auth.takeIntended())
  } else {
    triggerShake()
  }
}
</script>

<template>
  <div class="login">
    <div class="login__card" :class="{ 'is-shake': shake }">
      <div class="login__brand">
        <VipLogo variant="full" size="lg" decorative />
      </div>
      <h1 class="login__title">Sign in to Veltrix Intelligence</h1>
      <p class="login__sub">Enterprise analytics, pipelines and AI in one platform.</p>

      <VipAlert v-if="expired" tone="warning" title="Session expired"
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
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--vip-sp-8);
  background: var(--vip-bg-app);
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

@media (max-width: 480px) {
  .login {
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
