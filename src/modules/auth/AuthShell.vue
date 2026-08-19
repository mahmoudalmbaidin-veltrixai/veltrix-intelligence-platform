<script setup lang="ts">
/**
 * Shared enterprise authentication shell. Renders the same dark two-panel
 * experience as the Login page (brand aside + centered dark card) so every
 * pre-auth screen (Login, Forgot Password, Reset Password) reads as one system.
 * Presentational only — no auth logic. The card body is provided via the slot.
 */
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipLogo from '@/shared/ui/VipLogo.vue'

// Sales-safe V1 capability set — must match the Login aside (Phase 1 boundary).
const ecosystem: { icon: string; label: string }[] = [
  { icon: 'plug', label: 'Connection Studio' },
  { icon: 'workflow', label: 'Pipeline Studio' },
  { icon: 'database', label: 'Dataset & Semantic layer' },
  { icon: 'chart', label: 'Dashboard Studio' },
  { icon: 'shield', label: 'Governance & Security' },
]
</script>

<template>
  <div class="authshell">
    <!-- Brand experience panel — establishes enterprise credibility; hidden on small screens. -->
    <aside class="authshell__aside" aria-hidden="true">
      <div class="authshell__grid"></div>
      <div class="authshell__aside-inner">
        <VipLogo variant="full" size="lg" decorative />
        <h2 class="authshell__aside-title">
          One enterprise platform for connected data, governed analytics and dashboards.
        </h2>
        <p class="authshell__aside-lede">
          Veltrix unifies connections, pipelines, governed semantics and dashboards behind role-based control — so teams
          move from raw data to trusted decisions on a single, secure foundation.
        </p>
        <ul class="authshell__eco">
          <li v-for="cap in ecosystem" :key="cap.label" class="authshell__eco-item">
            <span class="authshell__eco-icon"><VipIcon :name="cap.icon" :size="16" /></span>
            <span>{{ cap.label }}</span>
          </li>
        </ul>
        <div class="authshell__trust">
          <span class="authshell__trust-item"><VipIcon name="shield" :size="14" /> Governed access</span>
          <span class="authshell__trust-item"><VipIcon name="lock" :size="14" /> Encrypted secrets</span>
          <span class="authshell__trust-item"><VipIcon name="layers" :size="14" /> Multi-tenant</span>
        </div>
      </div>
    </aside>

    <!-- Authentication panel -->
    <div class="authshell__panel">
      <div class="authshell__card">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.authshell {
  position: fixed;
  inset: 0;
  overflow-y: auto;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: var(--vip-bg-app);
}

/* ---- Brand experience panel (left) ---- */
.authshell__aside {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  padding: var(--vip-sp-9);
  color: #eaf0fb;
  background:
    radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, var(--vip-brand-500) 42%, transparent), transparent 60%),
    linear-gradient(160deg, #0b1220 0%, #111c30 55%, #0d1728 100%);
}
.authshell__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(color-mix(in srgb, #ffffff 6%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, #ffffff 6%, transparent) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(circle at 30% 40%, #000 0%, transparent 72%);
  pointer-events: none;
}
.authshell__aside-inner {
  position: relative;
  max-width: 460px;
  margin-inline: auto;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-6);
}
.authshell__aside-inner :deep(svg),
.authshell__aside-inner :deep(.vip-logo) {
  color: #fff;
}
.authshell__aside-title {
  font-size: var(--vip-fs-2xl);
  font-weight: var(--vip-fw-semibold);
  line-height: 1.25;
  letter-spacing: -0.01em;
  max-width: 22ch;
}
.authshell__aside-lede {
  font-size: var(--vip-fs-md);
  line-height: 1.6;
  color: color-mix(in srgb, #eaf0fb 78%, transparent);
}
.authshell__eco {
  list-style: none;
  margin: var(--vip-sp-2) 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vip-sp-3) var(--vip-sp-5);
}
.authshell__eco-item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
  color: color-mix(in srgb, #eaf0fb 90%, transparent);
}
.authshell__eco-icon {
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
.authshell__trust {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vip-sp-3) var(--vip-sp-5);
  margin-top: var(--vip-sp-4);
  padding-top: var(--vip-sp-5);
  border-top: 1px solid color-mix(in srgb, #ffffff 12%, transparent);
}
.authshell__trust-item {
  display: inline-flex;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-xs);
  font-weight: var(--vip-fw-medium);
  color: color-mix(in srgb, #eaf0fb 72%, transparent);
}

/* ---- Authentication panel (right) ---- */
.authshell__panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--vip-sp-8);
}
.authshell__card {
  width: 100%;
  max-width: 408px;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-xl);
  padding: var(--vip-sp-9);
  box-shadow: var(--vip-shadow-lg);
}

/* Collapse to a single, auth-focused column; drop the brand panel. */
@media (max-width: 960px) {
  .authshell {
    grid-template-columns: 1fr;
  }
  .authshell__aside {
    display: none;
  }
}
@media (max-width: 480px) {
  .authshell__panel {
    align-items: flex-start;
    padding: var(--vip-sp-4);
  }
  .authshell__card {
    padding: var(--vip-sp-6);
  }
}
</style>
