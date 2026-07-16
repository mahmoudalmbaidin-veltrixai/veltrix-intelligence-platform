<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <header class="vip-page-header">
    <div class="vip-page-header__main">
      <div class="vip-page-header__titles">
        <div class="vip-page-header__title-row">
          <h1 class="vip-page-header__title">{{ title }}</h1>
          <slot name="status" />
        </div>
        <p v-if="description" class="vip-page-header__desc">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="vip-page-header__actions"><slot name="actions" /></div>
    </div>
    <div v-if="$slots.tabs" class="vip-page-header__tabs"><slot name="tabs" /></div>
  </header>
</template>

<style scoped>
.vip-page-header { display: flex; flex-direction: column; gap: var(--vip-sp-6); margin-bottom: var(--vip-sp-7); }
.vip-page-header__main { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--vip-sp-7); flex-wrap: wrap; }
.vip-page-header__title-row { display: flex; align-items: center; gap: var(--vip-sp-5); }
.vip-page-header__title { font-size: var(--vip-fs-2xl); font-weight: var(--vip-fw-semibold); }
.vip-page-header__desc { font-size: var(--vip-fs-md); color: var(--vip-text-muted); margin-top: var(--vip-sp-3); max-width: 720px; }
.vip-page-header__actions { display: flex; align-items: center; gap: var(--vip-sp-4); }
</style>
