<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useUiStore } from '@/shared/stores/ui'
import VipCheckbox from '@/shared/ui/VipCheckbox.vue'
import VipSelect from '@/shared/ui/VipSelect.vue'
import { safeErrorText } from '@/shared/lib/safeError'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipSegmented from '@/shared/ui/VipSegmented.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipDialog from '@/shared/ui/VipDialog.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import {
  platformService,
  type PlatformOverview,
  type PlatformOrganizationRow,
  type PlatformOrganizationDetail,
  type PlatformUserRow,
} from './platform.service'

const ui = useUiStore()
const tab = ref<'overview' | 'organizations' | 'users'>('overview')

const overview = ref<PlatformOverview | null>(null)
const orgs = ref<PlatformOrganizationRow[]>([])
const orgSearch = ref('')
const users = ref<PlatformUserRow[]>([])
const userSearch = ref('')
const loading = ref(false)
const busyId = ref<string | null>(null)

// Create-organization dialog
const createOpen = ref(false)
const createPending = ref(false)
const createError = ref<string | null>(null)
const form = ref({ name: '', slug: '', owner_email: '' })

// Create-user (direct provisioning) dialog
const userCreateOpen = ref(false)
const userCreatePending = ref(false)
const userCreateError = ref<string | null>(null)
const showPassword = ref(false)
const userForm = ref({
  username: '',
  display_name: '',
  email: '',
  password: '',
  is_platform_admin: false,
  organization_id: '',
  organization_role: 'organization_member',
})
// Username: required, lowercase letters/numbers/._- ; email is OPTIONAL.
const usernameValid = computed(() => /^[a-z0-9][a-z0-9._-]{2,}$/.test(userForm.value.username.trim().toLowerCase()))
const orgRoleOptions = [
  { value: 'organization_admin', label: 'Admin — manage the org, members and content' },
  { value: 'organization_member', label: 'Member — use the org’s modules' },
]
const orgOptions = computed(() => [
  { value: '', label: 'No organization (create/assign later)' },
  ...orgs.value.map((o) => ({ value: o.id, label: `${o.name} · ${o.slug}` })),
])
// Credentials to share once, shown after a successful create.
const createdCreds = ref<{ username: string; password: string } | null>(null)
const userEmailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(userForm.value.email.trim()))

// Organization detail dialog
const detail = ref<PlatformOrganizationDetail | null>(null)

function tone(status: string): 'success' | 'warning' | 'neutral' | 'danger' {
  if (status === 'active') return 'success'
  if (status === 'suspended') return 'warning'
  if (status === 'archived' || status === 'deleted') return 'danger'
  return 'neutral'
}
function slugify(v: string): string {
  return v
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100)
}

async function loadOverview() {
  overview.value = await platformService.overview()
}
async function loadOrgs() {
  loading.value = true
  try {
    orgs.value = (await platformService.organizations(1, 100, orgSearch.value || undefined)).items
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Organizations failed to load', message: safeErrorText(error) })
  } finally {
    loading.value = false
  }
}
async function loadUsers() {
  loading.value = true
  try {
    users.value = (await platformService.users(1, 100, userSearch.value || undefined)).items
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Users failed to load', message: safeErrorText(error) })
  } finally {
    loading.value = false
  }
}

function switchTab(next: string) {
  tab.value = next as typeof tab.value
  if (next === 'organizations' && !orgs.value.length) void loadOrgs()
  if (next === 'users' && !users.value.length) void loadUsers()
}

async function toggleOrg(row: PlatformOrganizationRow) {
  busyId.value = row.id
  try {
    const updated =
      row.status === 'suspended'
        ? await platformService.activateOrganization(row.id)
        : await platformService.suspendOrganization(row.id)
    row.status = updated.status
    ui.pushToast({ kind: 'success', title: `Organization ${updated.status}`, message: row.name })
    await loadOverview()
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Action failed', message: safeErrorText(error) })
  } finally {
    busyId.value = null
  }
}
async function toggleUser(row: PlatformUserRow) {
  busyId.value = row.id
  try {
    const updated =
      row.status === 'suspended'
        ? await platformService.activateUser(row.id)
        : await platformService.suspendUser(row.id)
    row.status = updated.status
    ui.pushToast({ kind: 'success', title: `User ${updated.status}`, message: row.email ?? `@${row.username}` })
    await loadOverview()
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Action failed', message: safeErrorText(error) })
  } finally {
    busyId.value = null
  }
}

function openCreate() {
  form.value = { name: '', slug: '', owner_email: '' }
  createError.value = null
  createOpen.value = true
}

// --- Create user (direct provisioning) ---
function generatePassword(): string {
  // Cryptographically strong, human-shareable (no ambiguous chars).
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%*?'
  const bytes = new Uint32Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('')
}
function openCreateUser() {
  userForm.value = {
    username: '',
    display_name: '',
    email: '',
    password: generatePassword(),
    is_platform_admin: false,
    organization_id: '',
    organization_role: 'organization_member',
  }
  showPassword.value = true
  userCreateError.value = null
  createdCreds.value = null
  userCreateOpen.value = true
  // Ensure the org dropdown is populated even if the operator hasn't opened the Orgs tab.
  if (!orgs.value.length) void loadOrgs()
}
async function copyText(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    ui.pushToast({ kind: 'success', title: `${label} copied` })
  } catch {
    ui.pushToast({ kind: 'info', title: 'Copy manually', message: 'Clipboard is unavailable in this context.' })
  }
}
async function submitCreateUser() {
  const emailProvided = userForm.value.email.trim().length > 0
  if (
    !usernameValid.value ||
    userForm.value.display_name.trim().length < 1 ||
    userForm.value.password.length < 12 ||
    (emailProvided && !userEmailValid.value)
  ) {
    userCreateError.value =
      'Enter a valid username, a full name, a password of at least 12 characters, and a valid email if provided.'
    return
  }
  userCreatePending.value = true
  userCreateError.value = null
  try {
    const assignOrg = userForm.value.organization_id !== ''
    const created = await platformService.createUser({
      username: userForm.value.username.trim(),
      display_name: userForm.value.display_name.trim(),
      email: emailProvided ? userForm.value.email.trim() : null,
      password: userForm.value.password,
      is_platform_admin: userForm.value.is_platform_admin,
      organization_id: assignOrg ? userForm.value.organization_id : null,
      organization_role: assignOrg ? userForm.value.organization_role : null,
    })
    // Surface the credentials once so the operator can share them securely.
    createdCreds.value = { username: created.username, password: userForm.value.password }
    ui.pushToast({ kind: 'success', title: 'User created', message: `@${created.username}` })
    await Promise.all([loadUsers(), loadOverview()])
  } catch (error) {
    userCreateError.value = safeErrorText(error)
  } finally {
    userCreatePending.value = false
  }
}
async function submitCreate() {
  if (!form.value.name.trim() || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(form.value.slug)) {
    createError.value = 'Enter a name and a valid slug (lowercase letters, numbers, hyphens).'
    return
  }
  createPending.value = true
  createError.value = null
  try {
    const created = await platformService.createOrganization({
      name: form.value.name.trim(),
      slug: form.value.slug,
      owner_email: form.value.owner_email.trim() || null,
    })
    createOpen.value = false
    ui.pushToast({ kind: 'success', title: 'Organization created', message: created.name })
    await Promise.all([loadOrgs(), loadOverview()])
  } catch (error) {
    createError.value = safeErrorText(error)
  } finally {
    createPending.value = false
  }
}

async function openDetail(row: PlatformOrganizationRow) {
  try {
    detail.value = await platformService.organization(row.id)
  } catch (error) {
    ui.pushToast({ kind: 'error', title: 'Detail failed to load', message: safeErrorText(error) })
  }
}

onMounted(loadOverview)
</script>

<template>
  <div class="pa">
    <VipPageHeader
      title="Platform administration"
      description="Cross-tenant operator console. Manage every organization, workspace and user."
    >
      <template #actions>
        <VipButton variant="primary" icon="plus" @click="openCreate">New organization</VipButton>
      </template>
    </VipPageHeader>

    <VipSegmented
      :model-value="tab"
      :options="[
        { value: 'overview', label: 'Overview' },
        { value: 'organizations', label: 'Organizations' },
        { value: 'users', label: 'Users' },
      ]"
      @update:model-value="switchTab"
    />

    <!-- Overview -->
    <section v-if="tab === 'overview'" class="pa__section">
      <div v-if="overview" class="pa__stats">
        <div class="pa__stat">
          <span class="pa__stat-value">{{ overview.organizations_total }}</span>
          <span class="pa__stat-label">Organizations</span>
          <span class="pa__stat-sub"
            >{{ overview.organizations_active }} active · {{ overview.organizations_suspended }} suspended</span
          >
        </div>
        <div class="pa__stat">
          <span class="pa__stat-value">{{ overview.workspaces_total }}</span>
          <span class="pa__stat-label">Workspaces</span>
        </div>
        <div class="pa__stat">
          <span class="pa__stat-value">{{ overview.users_total }}</span>
          <span class="pa__stat-label">Users</span>
          <span class="pa__stat-sub"
            >{{ overview.users_active }} active · {{ overview.users_suspended }} suspended</span
          >
        </div>
        <div class="pa__stat">
          <span class="pa__stat-value">{{ overview.platform_admins }}</span>
          <span class="pa__stat-label">Platform admins</span>
        </div>
      </div>
      <div v-else class="pa__loading">Loading overview…</div>
    </section>

    <!-- Organizations -->
    <section v-else-if="tab === 'organizations'" class="pa__section">
      <div class="pa__toolbar">
        <VipInput
          v-model="orgSearch"
          icon="search"
          placeholder="Search organizations…"
          size="sm"
          @keyup.enter="loadOrgs"
        />
        <VipButton variant="tertiary" size="sm" @click="loadOrgs">Search</VipButton>
      </div>
      <div v-if="loading" class="pa__loading">Loading…</div>
      <table v-else-if="orgs.length" class="pa__table">
        <thead>
          <tr>
            <th>Organization</th>
            <th>Status</th>
            <th>Members</th>
            <th>Workspaces</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orgs" :key="o.id">
            <td>
              <button class="pa__link" @click="openDetail(o)">{{ o.name }}</button>
              <div class="pa__muted">{{ o.slug }}</div>
            </td>
            <td>
              <VipBadge :tone="tone(o.status)" size="sm">{{ o.status }}</VipBadge>
            </td>
            <td>{{ o.member_count }}</td>
            <td>{{ o.workspace_count }}</td>
            <td class="pa__muted">{{ relativeTime(o.created_at) }}</td>
            <td class="pa__actions">
              <VipButton
                :variant="o.status === 'suspended' ? 'secondary' : 'tertiary'"
                size="xs"
                :loading="busyId === o.id"
                @click="toggleOrg(o)"
                >{{ o.status === 'suspended' ? 'Activate' : 'Suspend' }}</VipButton
              >
              <VipButton variant="ghost" size="xs" @click="openDetail(o)">View</VipButton>
            </td>
          </tr>
        </tbody>
      </table>
      <VipEmptyState v-else icon="search" title="No organizations" description="Try another search." />
    </section>

    <!-- Users -->
    <section v-else class="pa__section">
      <div class="pa__toolbar">
        <VipInput v-model="userSearch" icon="search" placeholder="Search users…" size="sm" @keyup.enter="loadUsers" />
        <VipButton variant="tertiary" size="sm" @click="loadUsers">Search</VipButton>
        <VipButton variant="primary" size="sm" icon="plus" @click="openCreateUser">New user</VipButton>
      </div>
      <div v-if="loading" class="pa__loading">Loading…</div>
      <table v-else-if="users.length" class="pa__table">
        <thead>
          <tr>
            <th>User</th>
            <th>Status</th>
            <th>Orgs</th>
            <th>Platform admin</th>
            <th>Last login</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>
              <div>
                {{ u.display_name }} <span class="pa__uname">@{{ u.username }}</span>
              </div>
              <div class="pa__muted">
                <template v-if="u.email">{{ u.email }}</template>
                <span v-else class="pa__no-email">No email configured</span>
              </div>
            </td>
            <td>
              <VipBadge :tone="tone(u.status)" size="sm">{{ u.status }}</VipBadge>
            </td>
            <td>{{ u.organization_count }}</td>
            <td>
              <VipBadge v-if="u.is_platform_admin" tone="info" size="sm">Admin</VipBadge>
              <span v-else class="pa__muted">—</span>
            </td>
            <td class="pa__muted">{{ u.last_login_at ? relativeTime(u.last_login_at) : 'never' }}</td>
            <td class="pa__actions">
              <VipButton
                :variant="u.status === 'suspended' ? 'secondary' : 'tertiary'"
                size="xs"
                :loading="busyId === u.id"
                @click="toggleUser(u)"
                >{{ u.status === 'suspended' ? 'Activate' : 'Suspend' }}</VipButton
              >
            </td>
          </tr>
        </tbody>
      </table>
      <VipEmptyState v-else icon="search" title="No users" description="Try another search." />
    </section>

    <!-- Create organization -->
    <VipDialog
      :open="createOpen"
      title="New organization"
      description="Provision a fully isolated organization. Optionally assign an existing user as owner."
      @close="createOpen = false"
    >
      <div class="pa__form">
        <VipInput
          v-model="form.name"
          label="Organization name"
          placeholder="Acme Corporation"
          @input="form.slug = slugify(form.name)"
        />
        <VipInput v-model="form.slug" label="Slug" help="Lowercase letters, numbers and hyphens." />
        <VipInput
          v-model="form.owner_email"
          label="Owner email (optional)"
          help="An existing user's email. Defaults to you if left blank."
        />
        <p v-if="createError" class="pa__error" role="alert">{{ createError }}</p>
      </div>
      <template #footer>
        <VipButton variant="tertiary" :disabled="createPending" @click="createOpen = false">Cancel</VipButton>
        <VipButton variant="primary" :loading="createPending" @click="submitCreate">Create organization</VipButton>
      </template>
    </VipDialog>

    <!-- Create user (direct provisioning) -->
    <VipDialog
      :open="userCreateOpen"
      title="New user"
      description="Provision an account directly. You set the initial password and share it securely with the person."
      :closable="!userCreatePending"
      @close="userCreateOpen = false"
    >
      <div v-if="!createdCreds" class="pa__form">
        <VipInput v-model="userForm.display_name" label="Full name" placeholder="Jane Cooper" />
        <VipInput
          v-model="userForm.username"
          label="Username (login identifier)"
          placeholder="jane.cooper"
          help="Required. Lowercase letters, numbers, dot, dash or underscore."
        />
        <VipInput
          v-model="userForm.email"
          label="Email (optional)"
          type="email"
          placeholder="jane@company.com"
          help="Leave blank if the person has no email — email features simply stay disabled."
        />
        <div class="pa__pw">
          <VipInput
            v-model="userForm.password"
            label="Initial password"
            :type="showPassword ? 'text' : 'password'"
            help="At least 12 characters. Generated automatically — the user can change it after first sign-in."
          />
          <div class="pa__pw-actions">
            <VipButton variant="tertiary" size="xs" icon="refresh" @click="userForm.password = generatePassword()"
              >Regenerate</VipButton
            >
            <VipButton
              variant="tertiary"
              size="xs"
              :icon="showPassword ? 'eyeOff' : 'eye'"
              @click="showPassword = !showPassword"
              >{{ showPassword ? 'Hide' : 'Show' }}</VipButton
            >
          </div>
        </div>
        <VipSelect
          v-model="userForm.organization_id"
          label="Assign to organization"
          :options="orgOptions"
          help="Gives them access to this org’s modules and its default workspace."
        />
        <VipSelect
          v-if="userForm.organization_id"
          v-model="userForm.organization_role"
          label="Organization role"
          :options="orgRoleOptions"
        />
        <VipCheckbox v-model="userForm.is_platform_admin" label="Grant platform-admin access (cross-tenant console)" />
        <p class="pa__hint">
          The person signs in with their <strong>username + password</strong>. Pick an organization + role here to grant
          modules immediately, or leave it unassigned and add them later from an org’s <em>Members &amp; Roles</em>.
        </p>
        <p v-if="userCreateError" class="pa__error" role="alert">{{ userCreateError }}</p>
      </div>

      <!-- Share-credentials result (shown once) -->
      <div v-else class="pa__creds">
        <p class="pa__creds-lead">
          Account created. Share these credentials securely — the password is shown only once.
        </p>
        <div class="pa__cred-row">
          <span class="pa__cred-label">Username</span>
          <code class="pa__cred-value">{{ createdCreds.username }}</code>
          <VipButton variant="tertiary" size="xs" icon="copy" @click="copyText(createdCreds.username, 'Username')"
            >Copy</VipButton
          >
        </div>
        <div class="pa__cred-row">
          <span class="pa__cred-label">Password</span>
          <code class="pa__cred-value">{{ createdCreds.password }}</code>
          <VipButton variant="tertiary" size="xs" icon="copy" @click="copyText(createdCreds.password, 'Password')"
            >Copy</VipButton
          >
        </div>
      </div>

      <template #footer>
        <template v-if="!createdCreds">
          <VipButton variant="tertiary" :disabled="userCreatePending" @click="userCreateOpen = false">Cancel</VipButton>
          <VipButton
            variant="primary"
            :loading="userCreatePending"
            :disabled="!usernameValid || !userForm.display_name.trim()"
            @click="submitCreateUser"
            >Create user</VipButton
          >
        </template>
        <VipButton v-else variant="primary" @click="userCreateOpen = false">Done</VipButton>
      </template>
    </VipDialog>

    <!-- Organization detail -->
    <VipDialog
      :open="!!detail"
      :title="detail?.name ?? ''"
      :description="detail ? `${detail.slug} · ${detail.status}` : ''"
      size="lg"
      @close="detail = null"
    >
      <div v-if="detail" class="pa__detail">
        <h4>Workspaces ({{ detail.workspaces.length }})</h4>
        <ul class="pa__list">
          <li v-for="w in detail.workspaces" :key="w.id">
            {{ w.name }} <span class="pa__muted">· {{ w.slug }} · {{ w.status }}</span>
            <VipBadge v-if="w.is_default" tone="neutral" size="sm">default</VipBadge>
          </li>
        </ul>
        <h4>Members ({{ detail.members.length }})</h4>
        <ul class="pa__list">
          <li v-for="m in detail.members" :key="m.user_id">
            {{ m.display_name }} <span class="pa__muted">· {{ m.email }} · {{ m.role }} · {{ m.status }}</span>
          </li>
        </ul>
      </div>
      <template #footer>
        <VipButton variant="tertiary" @click="detail = null">Close</VipButton>
      </template>
    </VipDialog>
  </div>
</template>

<style scoped>
.pa__section {
  margin-top: var(--vip-sp-6);
}
.pa__stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--vip-sp-5);
}
.pa__stat {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  padding: var(--vip-sp-6);
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
}
.pa__stat-value {
  font-size: var(--vip-fs-2xl);
  font-weight: var(--vip-fw-bold);
}
.pa__stat-label {
  font-weight: var(--vip-fw-medium);
}
.pa__stat-sub,
.pa__muted {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
.pa__toolbar {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  margin-bottom: var(--vip-sp-5);
}
.pa__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--vip-fs-md);
}
.pa__table th,
.pa__table td {
  text-align: left;
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border-bottom: 1px solid var(--vip-border-subtle);
  vertical-align: top;
}
.pa__table th {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
}
.pa__actions {
  display: flex;
  gap: var(--vip-sp-2);
  justify-content: flex-end;
}
.pa__link {
  background: none;
  border: none;
  padding: 0;
  color: var(--vip-brand-500);
  font: inherit;
  cursor: pointer;
}
.pa__loading {
  color: var(--vip-text-muted);
  padding: var(--vip-sp-6) 0;
}
.pa__form {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.pa__error {
  color: var(--vip-danger-text);
  font-size: var(--vip-fs-sm);
}
.pa__detail h4 {
  margin: var(--vip-sp-5) 0 var(--vip-sp-3);
}
.pa__list {
  margin: 0;
  padding-left: var(--vip-sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.pa__pw {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-3);
}
.pa__pw-actions {
  display: flex;
  gap: var(--vip-sp-3);
}
.pa__hint {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  line-height: 1.5;
}
.pa__uname {
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.pa__no-email {
  font-style: italic;
  color: var(--vip-text-disabled);
}
.pa__creds {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-4);
}
.pa__creds-lead {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.pa__cred-row {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
}
.pa__cred-label {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  width: 68px;
  flex: none;
}
.pa__cred-value {
  flex: 1;
  min-width: 0;
  font-family: var(--vip-font-mono);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-primary);
  overflow-wrap: anywhere;
}
</style>
