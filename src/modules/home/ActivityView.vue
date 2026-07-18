<script setup lang="ts">
import { useQuery } from '@/shared/lib/query'
import { homeService } from './home.service'
import { relativeTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'

const { data } = useQuery('home:summary', () => homeService.summary())
</script>

<template>
  <div class="wrap">
    <VipPageHeader
      title="Recent activity"
      description="A chronological feed of events across your workspace resources."
    />
    <VipCard>
      <ul class="feed">
        <li v-for="a in data?.activity" :key="a.id" class="feed__item">
          <span class="feed__dot"><VipIcon :name="a.icon" :size="14" /></span>
          <div class="feed__body">
            <span class="feed__text"
              ><strong>{{ a.actor }}</strong> {{ a.action }} <strong>{{ a.target }}</strong></span
            >
            <span class="feed__time">{{ relativeTime(a.when) }}</span>
          </div>
        </li>
      </ul>
    </VipCard>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 860px;
}
.feed {
  list-style: none;
  margin: 0;
  padding: 0;
}
.feed__item {
  display: flex;
  gap: var(--vip-sp-5);
  padding: var(--vip-sp-5) 0;
  border-bottom: 1px solid var(--vip-border-subtle);
}
.feed__item:last-child {
  border-bottom: none;
}
.feed__dot {
  width: 30px;
  height: 30px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--vip-surface-3);
  color: var(--vip-text-muted);
}
.feed__body {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.feed__text {
  font-size: var(--vip-fs-md);
  color: var(--vip-text-secondary);
}
.feed__time {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-disabled);
}
</style>
