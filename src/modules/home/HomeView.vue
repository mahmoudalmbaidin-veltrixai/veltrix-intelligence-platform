<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useQuery } from '@/shared/lib/query'
import { homeService } from './home.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { ROLES } from '@/shared/permissions/roles'
import { QUICK_CREATE } from '@/app/navigation'
import { relativeTime } from '@/shared/lib/format'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipSkeleton from '@/shared/ui/VipSkeleton.vue'
import Sparkline from '@/shared/viz/Sparkline.vue'

const router = useRouter()
const platform = usePlatformStore()
const { data, isLoading } = useQuery('home:summary', () => homeService.summary())

const quickActions = QUICK_CREATE.filter((a) => !a.permission || platform.can(a.permission))
const hour = new Date().getHours()
const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
</script>

<template>
  <div class="home">
    <div class="home__hero">
      <div>
        <div class="home__greeting">{{ greeting }}, {{ platform.user.name.split(' ')[0] }}</div>
        <h1 class="home__title">{{ platform.workspace?.name }} workspace</h1>
        <p class="home__sub">{{ platform.organization.name }} · Signed in as {{ ROLES[platform.role].label }}</p>
      </div>
      <div class="home__quick">
        <VipButton
          v-for="a in quickActions"
          :key="a.to"
          :icon="a.icon"
          variant="secondary"
          size="sm"
          @click="router.push(a.to)"
          >{{ a.label.replace('New ', '') }}</VipButton
        >
      </div>
    </div>

    <!-- health -->
    <div class="home__health">
      <template v-if="isLoading">
        <VipCard v-for="n in 4" :key="n"
          ><VipSkeleton width="60%" /><VipSkeleton width="40%" height="24px" style="margin-top: 12px"
        /></VipCard>
      </template>
      <VipCard v-for="m in data?.health" v-else :key="m.label" class="health">
        <div class="health__top">
          <span class="health__icon" :class="`is-${m.tone}`"><VipIcon :name="m.icon" :size="16" /></span>
          <VipBadge v-if="m.delta" :tone="m.delta > 0 ? 'success' : 'danger'" size="sm"
            >{{ m.delta > 0 ? '+' : '' }}{{ m.delta }}%</VipBadge
          >
        </div>
        <div class="health__value">{{ m.value }}</div>
        <div class="health__label">{{ m.label }}</div>
        <div class="health__spark">
          <Sparkline :values="m.spark" :color="`var(--vip-${m.tone === 'neutral' ? 'brand-500' : m.tone})`" area />
        </div>
      </VipCard>
    </div>

    <div class="home__grid">
      <!-- recent -->
      <VipCard class="home__panel">
        <div class="panel__head">
          <h2 class="panel__title">Recent resources</h2>
          <VipButton variant="ghost" size="xs" icon-right="chevronRight" @click="router.push('/activity')"
            >View all</VipButton
          >
        </div>
        <ul class="reslist">
          <li v-for="r in data?.recent" :key="r.id" class="reslist__item" @click="router.push(r.to)">
            <VipIcon :name="r.icon" :size="16" class="reslist__icon" />
            <div class="reslist__body">
              <div class="reslist__name">{{ r.name }}</div>
              <div class="reslist__meta">{{ r.type }} · {{ relativeTime(r.when) }}</div>
            </div>
            <VipIcon name="chevronRight" :size="15" class="reslist__go" />
          </li>
        </ul>
      </VipCard>

      <!-- activity -->
      <VipCard class="home__panel">
        <div class="panel__head"><h2 class="panel__title">Activity</h2></div>
        <ul class="feed">
          <li v-for="a in data?.activity" :key="a.id" class="feed__item">
            <span class="feed__dot"><VipIcon :name="a.icon" :size="13" /></span>
            <div class="feed__body">
              <span class="feed__text"
                ><strong>{{ a.actor }}</strong> {{ a.action }} <strong>{{ a.target }}</strong></span
              >
              <span class="feed__time">{{ relativeTime(a.when) }}</span>
            </div>
          </li>
        </ul>
      </VipCard>

      <!-- checklist -->
      <VipCard class="home__panel">
        <div class="panel__head">
          <h2 class="panel__title">Getting started</h2>
          <VipBadge tone="brand" size="sm"
            >{{ data?.checklist.filter((c) => c.done).length }} / {{ data?.checklist.length }}</VipBadge
          >
        </div>
        <ul class="check">
          <li
            v-for="c in data?.checklist"
            :key="c.id"
            class="check__item"
            :class="{ 'is-done': c.done }"
            @click="router.push(c.to)"
          >
            <span class="check__box"><VipIcon v-if="c.done" name="check" :size="12" :stroke-width="3" /></span>
            <span class="check__label">{{ c.label }}</span>
            <VipIcon v-if="!c.done" name="chevronRight" :size="14" class="check__go" />
          </li>
        </ul>
        <div v-if="data?.pendingApprovals" class="home__approvals" @click="router.push('/automation/approvals')">
          <VipIcon name="check" :size="15" />
          <span>{{ data.pendingApprovals }} approvals awaiting your decision</span>
          <VipIcon name="chevronRight" :size="15" />
        </div>
      </VipCard>
    </div>
  </div>
</template>

<style scoped>
.home {
  max-width: 1400px;
  margin: 0 auto;
}
.home__hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--vip-sp-6);
  flex-wrap: wrap;
  margin-bottom: var(--vip-sp-8);
}
.home__greeting {
  color: var(--vip-brand-text);
  font-weight: var(--vip-fw-medium);
  font-size: var(--vip-fs-sm);
}
.home__title {
  font-size: var(--vip-fs-3xl);
  font-weight: var(--vip-fw-bold);
  margin-top: var(--vip-sp-2);
}
.home__sub {
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-3);
}
.home__quick {
  display: flex;
  gap: var(--vip-sp-3);
  flex-wrap: wrap;
}

.home__health {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--vip-sp-6);
  margin-bottom: var(--vip-sp-7);
}
.health__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.health__icon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-surface-3);
  color: var(--vip-text-secondary);
}
.health__icon.is-success {
  background: var(--vip-success-soft);
  color: var(--vip-success-text);
}
.health__icon.is-warning {
  background: var(--vip-warning-soft);
  color: var(--vip-warning-text);
}
.health__icon.is-danger {
  background: var(--vip-danger-soft);
  color: var(--vip-danger-text);
}
.health__icon.is-info {
  background: var(--vip-info-soft);
  color: var(--vip-info-text);
}
.health__value {
  font-size: var(--vip-fs-2xl);
  font-weight: var(--vip-fw-bold);
  margin-top: var(--vip-sp-5);
  font-variant-numeric: tabular-nums;
}
.health__label {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-2);
}
.health__spark {
  height: 34px;
  margin-top: var(--vip-sp-4);
}

.home__grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: var(--vip-sp-6);
  align-items: start;
}
.home__panel {
  padding: var(--vip-sp-6);
}
.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--vip-sp-5);
}
.panel__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}

.reslist,
.feed,
.check {
  list-style: none;
  margin: 0;
  padding: 0;
}
.reslist__item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4);
  border-radius: var(--vip-radius-md);
  cursor: pointer;
}
.reslist__item:hover {
  background: var(--vip-surface-hover);
}
.reslist__icon {
  color: var(--vip-text-muted);
}
.reslist__body {
  flex: 1;
  min-width: 0;
}
.reslist__name {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-medium);
}
.reslist__meta {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.reslist__go {
  color: var(--vip-text-disabled);
}

.feed__item {
  display: flex;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) 0;
}
.feed__dot {
  width: 26px;
  height: 26px;
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
  gap: 2px;
}
.feed__text {
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-secondary);
}
.feed__time {
  font-size: var(--vip-fs-2xs);
  color: var(--vip-text-disabled);
}

.check__item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4);
  border-radius: var(--vip-radius-md);
  cursor: pointer;
}
.check__item:hover {
  background: var(--vip-surface-hover);
}
.check__box {
  width: 18px;
  height: 18px;
  flex: none;
  border: 1.5px solid var(--vip-border-strong);
  border-radius: var(--vip-radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.check__item.is-done .check__box {
  background: var(--vip-success);
  border-color: var(--vip-success);
}
.check__label {
  flex: 1;
  font-size: var(--vip-fs-md);
}
.check__item.is-done .check__label {
  color: var(--vip-text-muted);
  text-decoration: line-through;
}
.check__go {
  color: var(--vip-text-disabled);
}
.home__approvals {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-5);
  padding: var(--vip-sp-5);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
  border-radius: var(--vip-radius-md);
  cursor: pointer;
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-medium);
}
.home__approvals span {
  flex: 1;
}

@media (max-width: 1200px) {
  .home__grid {
    grid-template-columns: 1fr 1fr;
  }
  .home__health {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 768px) {
  .home__grid,
  .home__health {
    grid-template-columns: 1fr;
  }
}
</style>
