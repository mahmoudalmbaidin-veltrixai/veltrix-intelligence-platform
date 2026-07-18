<script setup lang="ts">
/**
 * Full-bleed studio layout — no page padding, no app scroll. The studio views
 * (Pipeline, Dashboard, Explore, Report) render their own chrome + panels.
 */
</script>

<template>
  <div class="vip-studio-shell">
    <main id="vip-main" class="vip-studio-shell__main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.vip-studio-shell {
  height: 100vh;
  overflow: hidden;
  background: var(--vip-bg-canvas);
  display: flex;
}
.vip-studio-shell__main {
  flex: 1;
  min-width: 0;
  display: flex;
}
</style>
