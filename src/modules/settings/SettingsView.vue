<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlatformStore } from '@/shared/stores/platform'
import { useThemeStore, type Density, type ThemeMode } from '@/shared/stores/theme'
import { useAuthStore } from '@/shared/stores/auth'
import { useUiStore } from '@/shared/stores/ui'
import { useQuery } from '@/shared/lib/query'
import { relativeTime, formatDateTime } from '@/shared/lib/format'
import { authService } from '@/shared/services/auth'
import { settingsService, type ActiveSession } from './settings.service'
import { ApiError } from '@/shared/types/api'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipSwitch from '@/shared/ui/VipSwitch.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAvatar from '@/shared/ui/VipAvatar.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipConfirmDialog from '@/shared/ui/VipConfirmDialog.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const platform = usePlatformStore()
const theme = useThemeStore()
const auth = useAuthStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

/* ------------------------------------------------------------------ *
 * Information architecture (personal account only — org/workspace
 * administration lives in the dedicated Admin modules, never here).
 * ------------------------------------------------------------------ */
type SectionKey = 'profile' | 'security' | 'sessions' | 'appearance' | 'language' | 'account'
interface NavItem {
  key: SectionKey
  label: string
  icon: string
}
interface NavGroup {
  label: string
  items: NavItem[]
}
const groups: NavGroup[] = [
  {
    label: 'Account',
    items: [
      { key: 'profile', label: 'Profile', icon: 'users' },
      { key: 'security', label: 'Security', icon: 'shield' },
      { key: 'sessions', label: 'Sessions', icon: 'monitor' },
    ],
  },
  {
    label: 'Preferences',
    items: [
      { key: 'appearance', label: 'Appearance', icon: 'settings' },
      { key: 'language', label: 'Language & region', icon: 'globe' },
    ],
  },
  { label: 'Advanced', items: [{ key: 'account', label: 'Account information', icon: 'info' }] },
]
const validKeys = new Set(groups.flatMap((g) => g.items.map((i) => i.key)))
// Back-compat: old deep links (personal/notifications/etc.) resolve gracefully.
const LEGACY: Record<string, SectionKey> = {
  personal: 'profile',
  notifications: 'profile',
}
const active = computed<SectionKey>(() => {
  const raw = String(route.params.section ?? 'profile')
  if (validKeys.has(raw as SectionKey)) return raw as SectionKey
  return LEGACY[raw] ?? 'profile'
})
function go(key: SectionKey) {
  router.push({ name: 'settings', params: { section: key } })
}
const activeLabel = computed(
  () => groups.flatMap((g) => g.items).find((i) => i.key === active.value)?.label ?? 'Profile',
)

/* ------------------------------------------------------------------ *
 * Avatar (real, credentialed fetch → object URL)
 * ------------------------------------------------------------------ */
const avatarObjectUrl = ref<string | null>(null)
async function refreshAvatar() {
  const previous = avatarObjectUrl.value
  avatarObjectUrl.value = platform.user.avatarUrl ? await settingsService.fetchAvatarObjectUrl() : null
  if (previous) URL.revokeObjectURL(previous)
}
onMounted(refreshAvatar)
onBeforeUnmount(() => {
  if (avatarObjectUrl.value) URL.revokeObjectURL(avatarObjectUrl.value)
})

const fileInput = ref<HTMLInputElement | null>(null)
const avatarBusy = ref(false)
const isDragging = ref(false)
function pickAvatar() {
  fileInput.value?.click()
}
async function onAvatarFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) await uploadAvatar(file)
  if (fileInput.value) fileInput.value.value = ''
}
async function onAvatarDrop(event: DragEvent) {
  isDragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) await uploadAvatar(file)
}
async function uploadAvatar(file: File) {
  avatarBusy.value = true
  try {
    const session = await settingsService.uploadAvatar(file)
    platform.hydrateAuthenticatedUser(session.user)
    await refreshAvatar()
    ui.pushToast({ kind: 'success', title: 'Photo updated', message: 'Your profile picture was updated.' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Upload failed', message: errorMessage(error) })
  } finally {
    avatarBusy.value = false
  }
}
async function removeAvatar() {
  avatarBusy.value = true
  try {
    const session = await settingsService.removeAvatar()
    platform.hydrateAuthenticatedUser(session.user)
    await refreshAvatar()
    ui.pushToast({ kind: 'success', title: 'Photo removed', message: 'Your profile picture was removed.' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Could not remove photo', message: errorMessage(error) })
  } finally {
    avatarBusy.value = false
  }
}

/* ------------------------------------------------------------------ *
 * Profile form (dirty-tracked; identity fields are read-only)
 * ------------------------------------------------------------------ */
interface ProfileForm {
  displayName: string
  jobTitle: string
  department: string
  phone: string
}
function currentProfile(): ProfileForm {
  return {
    displayName: platform.user.name ?? '',
    jobTitle: platform.user.jobTitle ?? '',
    department: platform.user.department ?? '',
    phone: platform.user.phone ?? '',
  }
}
const profile = reactive<ProfileForm>(currentProfile())
watch(
  () => platform.user.id,
  () => Object.assign(profile, currentProfile()),
)
const profileDirty = computed(() => {
  const base = currentProfile()
  return (
    profile.displayName.trim() !== base.displayName ||
    profile.jobTitle !== base.jobTitle ||
    profile.department !== base.department ||
    profile.phone !== base.phone
  )
})
const profileSaving = ref(false)
const profileError = ref('')
async function saveProfile() {
  if (!profile.displayName.trim()) {
    profileError.value = 'A display name is required.'
    return
  }
  profileError.value = ''
  profileSaving.value = true
  try {
    const session = await settingsService.updateProfile({
      display_name: profile.displayName.trim(),
      job_title: profile.jobTitle.trim() || null,
      department: profile.department.trim() || null,
      phone: profile.phone.trim() || null,
    })
    platform.hydrateAuthenticatedUser(session.user)
    Object.assign(profile, currentProfile())
    ui.pushToast({ kind: 'success', title: 'Profile updated', message: 'Your changes were saved.' })
  } catch (error) {
    profileError.value = errorMessage(error)
    ui.pushToast({ kind: 'error', title: 'Could not update profile', message: profileError.value })
  } finally {
    profileSaving.value = false
  }
}

/* ------------------------------------------------------------------ *
 * Appearance — theme, density, reduced motion (persisted both to the
 * theme store for instant apply AND to server preferences).
 * ------------------------------------------------------------------ */
const themeOptions = [
  { value: 'light' as ThemeMode, label: 'Light', icon: 'sun' },
  { value: 'dark' as ThemeMode, label: 'Dark', icon: 'moon' },
  { value: 'system' as ThemeMode, label: 'System', icon: 'monitor' },
]
const densityOptions = [
  { value: 'comfortable' as Density, label: 'Comfortable' },
  { value: 'compact' as Density, label: 'Compact' },
]
async function persistPreferences(patch: Record<string, unknown>) {
  try {
    const session = await settingsService.updatePreferences(patch)
    platform.hydrateAuthenticatedUser(session.user)
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Could not save preference', message: errorMessage(error) })
  }
}
function setTheme(mode: ThemeMode) {
  theme.setMode(mode)
  void persistPreferences({ theme: mode })
}
function setDensity(value: Density) {
  theme.setDensity(value)
  void persistPreferences({ density: value })
}
function setReducedMotion(value: boolean) {
  theme.setReducedMotion(value)
  void persistPreferences({ reducedMotion: value })
}

/* ------------------------------------------------------------------ *
 * Language & region
 * ------------------------------------------------------------------ */
const localeOptions = [
  { value: 'en-US', label: 'English (United States)' },
  { value: 'en-GB', label: 'English (United Kingdom)' },
  { value: 'ar-SA', label: 'العربية (السعودية)' },
  { value: 'fr-FR', label: 'Français (France)' },
  { value: 'de-DE', label: 'Deutsch (Deutschland)' },
  { value: 'es-ES', label: 'Español (España)' },
]
const timezoneOptions = computed(() => {
  const intl = Intl as typeof Intl & { supportedValuesOf?: (key: 'timeZone') => string[] }
  const zones: string[] =
    typeof intl.supportedValuesOf === 'function'
      ? intl.supportedValuesOf('timeZone')
      : [platform.user.timezone || 'UTC']
  return zones.map((zone: string) => ({ value: zone, label: `${zone} · ${offsetLabel(zone)}` }))
})
function offsetLabel(zone: string): string {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: zone,
      timeZoneName: 'shortOffset',
    }).formatToParts(new Date())
    return parts.find((p) => p.type === 'timeZoneName')?.value ?? ''
  } catch {
    return ''
  }
}
const dateFormatOptions = [
  { value: 'YYYY-MM-DD', label: '2026-08-12 (ISO)' },
  { value: 'DD/MM/YYYY', label: '12/08/2026 (Day first)' },
  { value: 'MM/DD/YYYY', label: '08/12/2026 (Month first)' },
  { value: 'D MMM YYYY', label: '12 Aug 2026' },
]
const timeFormatOptions = [
  { value: '24h', label: '24-hour (14:30)' },
  { value: '12h', label: '12-hour (2:30 PM)' },
]
const firstDayOptions = [
  { value: 'monday', label: 'Monday' },
  { value: 'sunday', label: 'Sunday' },
  { value: 'saturday', label: 'Saturday' },
]
const region = reactive({
  locale: platform.user.locale || 'en-US',
  timezone: platform.user.timezone || 'UTC',
  dateFormat: String(platform.user.preferences?.dateFormat ?? 'YYYY-MM-DD'),
  timeFormat: String(platform.user.preferences?.timeFormat ?? '24h'),
  firstDayOfWeek: String(platform.user.preferences?.firstDayOfWeek ?? 'monday'),
})
const regionSaving = ref(false)
const regionDirty = computed(
  () =>
    region.locale !== (platform.user.locale || 'en-US') ||
    region.timezone !== (platform.user.timezone || 'UTC') ||
    region.dateFormat !== String(platform.user.preferences?.dateFormat ?? 'YYYY-MM-DD') ||
    region.timeFormat !== String(platform.user.preferences?.timeFormat ?? '24h') ||
    region.firstDayOfWeek !== String(platform.user.preferences?.firstDayOfWeek ?? 'monday'),
)
async function saveRegion() {
  regionSaving.value = true
  try {
    const session = await settingsService.updateProfile({
      locale: region.locale,
      timezone: region.timezone,
      preferences: {
        dateFormat: region.dateFormat,
        timeFormat: region.timeFormat,
        firstDayOfWeek: region.firstDayOfWeek,
      },
    })
    platform.hydrateAuthenticatedUser(session.user)
    ui.pushToast({
      kind: 'success',
      title: 'Preferences saved',
      message: 'Your language and region settings were saved.',
    })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Could not save', message: errorMessage(error) })
  } finally {
    regionSaving.value = false
  }
}

/* ------------------------------------------------------------------ *
 * Security — password change (backend revokes all sessions on change)
 * ------------------------------------------------------------------ */
const pwDialog = ref(false)
const pw = reactive({ current: '', next: '', confirm: '' })
const pwError = ref('')
const pwSaving = ref(false)
const pwStrong = computed(() => pw.next.length >= 12 && /[a-z]/i.test(pw.next) && /\d|\s|\W/.test(pw.next))
function openPasswordDialog() {
  pw.current = pw.next = pw.confirm = ''
  pwError.value = ''
  pwDialog.value = true
}
async function submitPassword() {
  if (pw.next !== pw.confirm) {
    pwError.value = 'The new passwords do not match.'
    return
  }
  if (!pwStrong.value) {
    pwError.value = 'Use at least 12 characters with a mix of letters and numbers or symbols.'
    return
  }
  pwError.value = ''
  pwSaving.value = true
  try {
    await authService.changePassword(pw.current, pw.next)
    pwDialog.value = false
    ui.pushToast({
      kind: 'success',
      title: 'Password changed',
      message: 'For your security you have been signed out on all devices.',
    })
    // The backend revokes every session on password change — return to sign-in.
    await auth.logout()
    await router.push({ name: 'login' })
  } catch (error) {
    pwError.value = errorMessage(error)
  } finally {
    pwSaving.value = false
  }
}

/* ------------------------------------------------------------------ *
 * Sessions
 * ------------------------------------------------------------------ */
const {
  data: sessions,
  isLoading: sessionsLoading,
  error: sessionsError,
  refetch: refetchSessions,
} = useQuery<ActiveSession[]>('settings:sessions', () => settingsService.listSessions())

const revokeTarget = ref<ActiveSession | null>(null)
const revokeBusy = ref(false)
const revokeOthersOpen = ref(false)
function confirmRevoke(session: ActiveSession) {
  revokeTarget.value = session
}
async function doRevoke() {
  if (!revokeTarget.value) return
  revokeBusy.value = true
  try {
    await settingsService.revokeSession(revokeTarget.value.id)
    revokeTarget.value = null
    await refetchSessions()
    ui.pushToast({ kind: 'success', title: 'Session signed out', message: 'The session was revoked.' })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Could not sign out session', message: errorMessage(error) })
  } finally {
    revokeBusy.value = false
  }
}
async function doRevokeOthers() {
  revokeBusy.value = true
  try {
    const count = await settingsService.revokeOtherSessions()
    revokeOthersOpen.value = false
    await refetchSessions()
    ui.pushToast({
      kind: 'success',
      title: 'Other sessions signed out',
      message: count
        ? `${count} other session${count === 1 ? '' : 's'} were signed out.`
        : 'No other sessions were active.',
    })
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Could not sign out sessions', message: errorMessage(error) })
  } finally {
    revokeBusy.value = false
  }
}
const activeSessionCount = computed(() => sessions.value?.length ?? 0)

/* ------------------------------------------------------------------ *
 * Contextual admin links (visibility ≠ authorization; backend decides)
 * ------------------------------------------------------------------ */
const canWorkspaceAdmin = computed(() => platform.can('workspace.update'))
const canOrgAdmin = computed(() => platform.can('governance.read'))

/* ------------------------------------------------------------------ */
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.fieldErrors?.[0]?.message ?? error.message ?? 'Something went wrong. Please try again.'
  }
  if (error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}
function initialsColor(): string {
  return platform.user.avatarColor || '#6d5efc'
}

/** Best-effort friendly device label from a User-Agent (never fabricated). */
function deviceLabel(ua: string | null): string {
  if (!ua) return 'Browser session'
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /Chrome\//.test(ua)
      ? 'Chrome'
      : /Firefox\//.test(ua)
        ? 'Firefox'
        : /Safari\//.test(ua)
          ? 'Safari'
          : 'Browser'
  const os = /Windows/.test(ua)
    ? 'Windows'
    : /Macintosh|Mac OS/.test(ua)
      ? 'macOS'
      : /Android/.test(ua)
        ? 'Android'
        : /iPhone|iPad|iOS/.test(ua)
          ? 'iOS'
          : /Linux/.test(ua)
            ? 'Linux'
            : ''
  return os ? `${browser} on ${os}` : browser
}
</script>

<template>
  <div class="settings">
    <VipPageHeader
      title="Settings"
      description="Manage your account, personal preferences, security, and notification settings."
    />

    <div class="settings__layout">
      <!-- Section navigation (rail on desktop, select on mobile) -->
      <nav class="settings__nav" aria-label="Settings sections">
        <div class="settings__nav-mobile">
          <VipSelect
            :model-value="active"
            :options="groups.flatMap((g) => g.items).map((i) => ({ value: i.key, label: i.label }))"
            label="Section"
            @update:model-value="(v: string) => go(v as SectionKey)"
          />
        </div>
        <div v-for="group in groups" :key="group.label" class="settings__nav-group">
          <p class="settings__nav-label">{{ group.label }}</p>
          <button
            v-for="item in group.items"
            :key="item.key"
            type="button"
            class="settings__nav-item"
            :class="{ 'is-active': active === item.key }"
            :aria-current="active === item.key ? 'page' : undefined"
            @click="go(item.key)"
          >
            <VipIcon :name="item.icon" :size="16" />
            <span>{{ item.label }}</span>
          </button>
        </div>
      </nav>

      <section class="settings__content" :aria-label="activeLabel">
        <!-- ============================ PROFILE ============================ -->
        <template v-if="active === 'profile'">
          <VipCard>
            <div class="settings__identity">
              <div
                class="settings__avatar-drop"
                :class="{ 'is-dragging': isDragging }"
                @click="pickAvatar"
                @keydown.enter.prevent="pickAvatar"
                @dragover.prevent="isDragging = true"
                @dragleave.prevent="isDragging = false"
                @drop.prevent="onAvatarDrop"
                role="button"
                tabindex="0"
                :aria-label="'Change profile photo'"
              >
                <VipAvatar
                  :name="platform.user.name || 'You'"
                  :color="initialsColor()"
                  :src="avatarObjectUrl"
                  :size="76"
                />
                <span v-if="avatarBusy" class="settings__avatar-busy">Uploading…</span>
              </div>
              <div class="settings__identity-meta">
                <h2 class="settings__identity-name">{{ platform.user.name || 'Your name' }}</h2>
                <p class="settings__identity-sub">
                  {{ platform.user.jobTitle || 'Add a job title' }}
                  <span v-if="platform.user.email"> · {{ platform.user.email }}</span>
                </p>
                <div class="settings__avatar-actions">
                  <VipButton size="sm" variant="secondary" icon="upload" :loading="avatarBusy" @click="pickAvatar">
                    {{ platform.user.avatarUrl ? 'Change photo' : 'Upload photo' }}
                  </VipButton>
                  <VipButton
                    v-if="platform.user.avatarUrl"
                    size="sm"
                    variant="tertiary"
                    :disabled="avatarBusy"
                    @click="removeAvatar"
                  >
                    Remove
                  </VipButton>
                </div>
                <p class="settings__hint">PNG or JPEG, up to 5 MB.</p>
              </div>
              <input
                ref="fileInput"
                type="file"
                accept="image/png,image/jpeg"
                class="settings__file"
                @change="onAvatarFile"
              />
            </div>
          </VipCard>

          <VipCard title="Personal information">
            <div class="settings__form">
              <VipInput v-model="profile.displayName" label="Full name" required />
              <div class="settings__readonly">
                <label>Username</label>
                <div class="settings__readonly-value">
                  {{ platform.user.username || '—'
                  }}<VipBadge tone="neutral" size="sm" variant="soft">Managed by your account</VipBadge>
                </div>
              </div>
              <div class="settings__readonly">
                <label>Email</label>
                <div class="settings__readonly-value">
                  {{ platform.user.email || 'No email on file'
                  }}<VipBadge tone="neutral" size="sm" variant="soft">Administrator managed</VipBadge>
                </div>
              </div>
              <div class="settings__form-row">
                <VipInput v-model="profile.jobTitle" label="Job title" placeholder="e.g. Data Platform Lead" />
                <VipInput v-model="profile.department" label="Department" placeholder="e.g. Analytics" />
              </div>
              <VipInput v-model="profile.phone" label="Phone" placeholder="+966 5X XXX XXXX" />
              <p v-if="profileError" class="settings__error">{{ profileError }}</p>
            </div>
            <template #footer>
              <div class="settings__actions">
                <span v-if="profileDirty" class="settings__dirty">Unsaved changes</span>
                <VipButton
                  variant="primary"
                  icon="check"
                  :loading="profileSaving"
                  :disabled="!profileDirty"
                  @click="saveProfile"
                >
                  Save changes
                </VipButton>
              </div>
            </template>
          </VipCard>
        </template>

        <!-- ============================ SECURITY ============================ -->
        <template v-else-if="active === 'security'">
          <VipCard title="Password">
            <div class="settings__status-row">
              <div>
                <p class="settings__status-title">Password</p>
                <p class="settings__hint">
                  Last changed
                  {{ platform.user.passwordChangedAt ? relativeTime(platform.user.passwordChangedAt) : 'unknown' }}
                </p>
              </div>
              <VipButton variant="secondary" icon="key" @click="openPasswordDialog">Change password</VipButton>
            </div>
          </VipCard>

          <VipCard title="Multi-factor authentication">
            <div class="settings__status-row">
              <div>
                <p class="settings__status-title">
                  Two-factor authentication <VipBadge tone="neutral" size="sm">Not available</VipBadge>
                </p>
                <p class="settings__hint">
                  Multi-factor authentication is not enabled on this deployment. Contact your administrator for account
                  protection options.
                </p>
              </div>
            </div>
          </VipCard>

          <VipCard title="Security status">
            <dl class="settings__facts">
              <div>
                <dt>Active sessions</dt>
                <dd>{{ activeSessionCount }}</dd>
              </div>
              <div>
                <dt>Password last changed</dt>
                <dd>{{ platform.user.passwordChangedAt ? formatDateTime(platform.user.passwordChangedAt) : '—' }}</dd>
              </div>
              <div>
                <dt>Sign-in method</dt>
                <dd>Password</dd>
              </div>
            </dl>
            <template #footer>
              <VipButton variant="tertiary" size="sm" @click="go('sessions')">Review active sessions →</VipButton>
            </template>
          </VipCard>
        </template>

        <!-- ============================ SESSIONS ============================ -->
        <template v-else-if="active === 'sessions'">
          <VipCard title="Active sessions">
            <p class="settings__hint settings__hint--block">
              These are the sessions currently signed in to your account. Sessions do not record device or location
              details, so only activity times are shown.
            </p>
            <div v-if="sessionsLoading" class="settings__muted">Loading sessions…</div>
            <div v-else-if="sessionsError" class="settings__retry">
              <span>We couldn't load your sessions. Your account is unaffected.</span>
              <VipButton size="sm" variant="secondary" @click="refetchSessions">Try again</VipButton>
            </div>
            <ul v-else class="settings__sessions">
              <li v-for="s in sessions ?? []" :key="s.id" class="settings__session">
                <VipIcon name="monitor" :size="18" />
                <div class="settings__session-meta">
                  <p class="settings__session-title">
                    {{ deviceLabel(s.userAgent) }}
                    <VipBadge v-if="s.current" tone="success" size="sm" variant="soft">Current session</VipBadge>
                  </p>
                  <p class="settings__hint">
                    Active {{ relativeTime(s.lastSeenAt) }} · Signed in {{ relativeTime(s.createdAt) }}
                  </p>
                </div>
                <VipButton v-if="!s.current" size="sm" variant="tertiary" @click="confirmRevoke(s)">
                  Sign out
                </VipButton>
              </li>
            </ul>
            <template #footer>
              <VipButton
                variant="secondary"
                icon="logout"
                :disabled="activeSessionCount <= 1"
                @click="revokeOthersOpen = true"
              >
                Sign out all other sessions
              </VipButton>
            </template>
          </VipCard>
        </template>

        <!-- ============================ APPEARANCE ============================ -->
        <template v-else-if="active === 'appearance'">
          <VipCard title="Theme">
            <p class="settings__hint settings__hint--block">
              Choose how VIP looks. System follows your device setting.
            </p>
            <VipSegmented
              :model-value="theme.mode"
              :options="themeOptions"
              @update:model-value="(v: ThemeMode) => setTheme(v)"
            />
          </VipCard>
          <VipCard title="Interface">
            <div class="settings__pref-row">
              <div>
                <p class="settings__status-title">Density</p>
                <p class="settings__hint">Compact tightens spacing across tables and lists.</p>
              </div>
              <VipSegmented
                :model-value="theme.density"
                :options="densityOptions"
                size="sm"
                @update:model-value="(v: Density) => setDensity(v)"
              />
            </div>
            <div class="settings__pref-row">
              <div>
                <p class="settings__status-title">Reduced motion</p>
                <p class="settings__hint">Minimise non-essential animation and transitions.</p>
              </div>
              <VipSwitch
                :model-value="theme.reducedMotion"
                label="Reduce motion"
                @update:model-value="(v: boolean) => setReducedMotion(v)"
              />
            </div>
          </VipCard>
        </template>

        <!-- ========================= LANGUAGE & REGION ========================= -->
        <template v-else-if="active === 'language'">
          <VipCard title="Language & region">
            <div class="settings__form">
              <VipSelect v-model="region.locale" :options="localeOptions" label="Interface language" />
              <p class="settings__hint">
                English is fully localized. Other languages set formatting and locale preferences; full interface
                translation may be partial.
              </p>
              <VipSelect v-model="region.timezone" :options="timezoneOptions" label="Time zone" />
              <div class="settings__form-row">
                <VipSelect v-model="region.dateFormat" :options="dateFormatOptions" label="Date format" />
                <VipSelect v-model="region.timeFormat" :options="timeFormatOptions" label="Time format" />
              </div>
              <VipSelect v-model="region.firstDayOfWeek" :options="firstDayOptions" label="First day of week" />
            </div>
            <template #footer>
              <div class="settings__actions">
                <span v-if="regionDirty" class="settings__dirty">Unsaved changes</span>
                <VipButton
                  variant="primary"
                  icon="check"
                  :loading="regionSaving"
                  :disabled="!regionDirty"
                  @click="saveRegion"
                >
                  Save changes
                </VipButton>
              </div>
            </template>
          </VipCard>
        </template>

        <!-- ========================= ACCOUNT INFORMATION ========================= -->
        <template v-else-if="active === 'account'">
          <VipCard title="Account information">
            <dl class="settings__facts">
              <div>
                <dt>Username</dt>
                <dd>{{ platform.user.username || '—' }}</dd>
              </div>
              <div>
                <dt>User ID</dt>
                <dd class="settings__mono">{{ platform.user.id || '—' }}</dd>
              </div>
              <div>
                <dt>Account type</dt>
                <dd>{{ platform.user.accountType || 'standard' }}</dd>
              </div>
              <div>
                <dt>Account created</dt>
                <dd>{{ platform.user.createdAt ? formatDateTime(platform.user.createdAt) : '—' }}</dd>
              </div>
              <div>
                <dt>Last sign-in</dt>
                <dd>{{ platform.user.lastLoginAt ? formatDateTime(platform.user.lastLoginAt) : '—' }}</dd>
              </div>
              <div>
                <dt>Sign-in method</dt>
                <dd>Password</dd>
              </div>
            </dl>
          </VipCard>

          <VipCard v-if="canWorkspaceAdmin || canOrgAdmin" title="Administration">
            <p class="settings__hint settings__hint--block">
              Organization and workspace administration live in their dedicated areas.
            </p>
            <div class="settings__admin-links">
              <RouterLink v-if="canWorkspaceAdmin" class="settings__admin-link" :to="{ name: 'admin-workspace' }">
                Open Workspace Management →
              </RouterLink>
              <RouterLink v-if="canOrgAdmin" class="settings__admin-link" :to="{ name: 'admin-org' }">
                Open Organization Administration →
              </RouterLink>
            </div>
          </VipCard>
        </template>
      </section>
    </div>

    <!-- Change password dialog -->
    <VipDialog
      :open="pwDialog"
      title="Change password"
      description="You'll be signed out on all devices after changing your password."
      size="sm"
      @close="pwDialog = false"
    >
      <div class="settings__form">
        <VipInput v-model="pw.current" type="password" label="Current password" required />
        <VipInput v-model="pw.next" type="password" label="New password" required />
        <VipInput v-model="pw.confirm" type="password" label="Confirm new password" required />
        <p class="settings__hint">At least 12 characters, mixing letters with numbers or symbols.</p>
        <p v-if="pwError" class="settings__error">{{ pwError }}</p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="pwDialog = false">Cancel</VipButton>
        <VipButton variant="primary" icon="check" :loading="pwSaving" @click="submitPassword"
          >Change password</VipButton
        >
      </template>
    </VipDialog>

    <!-- Revoke one session -->
    <VipConfirmDialog
      :open="!!revokeTarget"
      title="Sign out this session?"
      message="This device will be signed out immediately."
      confirm-label="Sign out"
      level="danger"
      :pending="revokeBusy"
      @confirm="doRevoke"
      @cancel="revokeTarget = null"
    />

    <!-- Revoke others -->
    <VipConfirmDialog
      :open="revokeOthersOpen"
      title="Sign out all other sessions?"
      message="Every session except this one will be signed out."
      confirm-label="Sign out others"
      level="danger"
      :pending="revokeBusy"
      @confirm="doRevokeOthers"
      @cancel="revokeOthersOpen = false"
    />
  </div>
</template>

<style scoped>
.settings {
  max-width: 1080px;
  margin: 0 auto;
  padding: var(--vip-sp-6);
}
.settings__layout {
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr);
  gap: var(--vip-sp-8);
  align-items: start;
}
.settings__nav {
  position: sticky;
  top: var(--vip-sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.settings__nav-mobile {
  display: none;
}
.settings__nav-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.settings__nav-label {
  font-size: var(--vip-fs-2xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vip-text-muted);
  margin: 0 0 var(--vip-sp-2) var(--vip-sp-3);
}
.settings__nav-item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-2) var(--vip-sp-3);
  border-radius: var(--vip-radius-md);
  border: none;
  background: none;
  color: var(--vip-text-secondary);
  font: inherit;
  font-size: var(--vip-fs-sm);
  text-align: left;
  cursor: pointer;
  width: 100%;
}
.settings__nav-item:hover {
  background: var(--vip-surface-2);
  color: var(--vip-text-primary);
}
.settings__nav-item.is-active {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text, var(--vip-brand-500));
  font-weight: var(--vip-fw-medium);
}
.settings__content {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
  min-width: 0;
}
.settings__identity {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-5);
  flex-wrap: wrap;
}
.settings__avatar-drop {
  position: relative;
  border-radius: 50%;
  cursor: pointer;
  outline-offset: 3px;
}
.settings__avatar-drop.is-dragging {
  outline: 2px dashed var(--vip-brand-500);
}
.settings__avatar-busy {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  border-radius: 50%;
  font-size: var(--vip-fs-2xs);
}
.settings__identity-meta {
  flex: 1;
  min-width: 200px;
}
.settings__identity-name {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
}
.settings__identity-sub {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  margin-top: 2px;
}
.settings__avatar-actions {
  display: flex;
  gap: var(--vip-sp-3);
  margin-top: var(--vip-sp-3);
}
.settings__file {
  display: none;
}
.settings__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-5);
}
.settings__form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-5);
}
.settings__readonly label {
  display: block;
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
  margin-bottom: var(--vip-sp-2);
}
.settings__readonly-value {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  color: var(--vip-text-primary);
}
.settings__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--vip-sp-4);
  width: 100%;
}
.settings__dirty {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
}
.settings__error {
  color: var(--vip-danger-text);
  font-size: var(--vip-fs-sm);
}
.settings__hint {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.settings__hint--block {
  margin-bottom: var(--vip-sp-4);
}
.settings__status-row,
.settings__pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
}
.settings__pref-row + .settings__pref-row {
  margin-top: var(--vip-sp-5);
  padding-top: var(--vip-sp-5);
  border-top: 1px solid var(--vip-border-subtle);
}
.settings__status-title {
  font-weight: var(--vip-fw-medium);
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
}
.settings__facts {
  display: flex;
  flex-direction: column;
}
.settings__facts > div {
  display: flex;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.settings__facts > div:last-child {
  border-bottom: none;
}
.settings__facts dt {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.settings__facts dd {
  color: var(--vip-text-primary);
  font-weight: var(--vip-fw-medium);
  text-align: right;
}
.settings__mono {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
}
.settings__sessions {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.settings__session {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.settings__session:last-child {
  border-bottom: none;
}
.settings__session-meta {
  flex: 1;
  min-width: 0;
}
.settings__session-title {
  font-weight: var(--vip-fw-medium);
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
}
.settings__muted {
  color: var(--vip-text-muted);
}
.settings__retry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.settings__admin-links {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.settings__admin-link {
  color: var(--vip-brand-text, var(--vip-brand-500));
  text-decoration: none;
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
}
.settings__admin-link:hover {
  text-decoration: underline;
}
@media (max-width: 860px) {
  .settings__layout {
    grid-template-columns: 1fr;
    gap: var(--vip-sp-5);
  }
  .settings__nav-group {
    display: none;
  }
  .settings__nav-mobile {
    display: block;
  }
  .settings__form-row {
    grid-template-columns: 1fr;
  }
}
</style>
