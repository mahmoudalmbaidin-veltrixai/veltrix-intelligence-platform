<template>
  <div class="vip-blank">
    <main id="vip-main" class="vip-blank__main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.vip-blank {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--vip-bg-app);
}
.vip-blank__main {
  width: 100%;
  max-width: 560px;
}
</style>
