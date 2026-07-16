<script setup lang="ts">
import AppSidebar from '@/app/shell/AppSidebar.vue'
import AppTopbar from '@/app/shell/AppTopbar.vue'
import MobileNav from '@/app/shell/MobileNav.vue'
import NotificationDrawer from '@/app/shell/NotificationDrawer.vue'
</script>

<template>
  <div class="vip-app">
    <AppSidebar class="vip-app__sidebar" />
    <div class="vip-app__col">
      <AppTopbar />
      <main id="vip-main" class="vip-app__main">
        <RouterView />
      </main>
    </div>
    <MobileNav />
    <NotificationDrawer />
  </div>
</template>

<style scoped>
.vip-app { display: flex; height: 100vh; overflow: hidden; background: var(--vip-bg-app); }
.vip-app__sidebar { flex: none; }
.vip-app__col { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.vip-app__main { flex: 1; overflow-y: auto; }
@media (max-width: 768px) { .vip-app__sidebar { display: none; } }
</style>
