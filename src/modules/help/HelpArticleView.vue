<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { getArticle, relatedArticles, categoryLabel } from './content'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipEmptyState from '@/shared/ui/VipEmptyState.vue'
import { useUiStore } from '@/shared/stores/ui'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()

const article = computed(() => getArticle(String(route.params.slug)))
const related = computed(() => (article.value ? relatedArticles(article.value) : []))

function markHelpful(helpful: boolean) {
  ui.pushToast({
    kind: helpful ? 'success' : 'info',
    title: helpful ? 'Thanks for the feedback' : 'Thanks — we’ll keep improving',
    message: helpful
      ? 'Glad this article helped.'
      : 'Sorry this wasn’t helpful. Try the search or contact support from Help & Docs.',
  })
}
</script>

<template>
  <div class="help-article">
    <template v-if="article">
      <nav class="help-article__breadcrumb" aria-label="Breadcrumb">
        <RouterLink :to="{ name: 'help' }">Help &amp; Docs</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ categoryLabel(article.category) }}</span>
        <span aria-hidden="true">/</span>
        <span class="help-article__crumb-current" aria-current="page">{{ article.title }}</span>
      </nav>

      <article>
        <header class="help-article__header">
          <h1 class="help-article__title">{{ article.title }}</h1>
          <p class="help-article__desc">{{ article.description }}</p>
        </header>

        <VipCard class="help-article__body">
          <template v-for="(block, index) in article.body" :key="index">
            <p v-if="block.kind === 'para'" class="help-article__para">{{ block.text }}</p>
            <h2 v-else-if="block.kind === 'subhead'" class="help-article__subhead">{{ block.text }}</h2>
            <ol v-else-if="block.kind === 'steps'" class="help-article__steps">
              <li v-for="(item, i) in block.items" :key="i">{{ item }}</li>
            </ol>
            <ul v-else-if="block.kind === 'list'" class="help-article__list">
              <li v-for="(item, i) in block.items" :key="i">{{ item }}</li>
            </ul>
            <p v-else-if="block.kind === 'note'" class="help-article__note">{{ block.text }}</p>
          </template>
        </VipCard>

        <section v-if="related.length" class="help-article__section" aria-label="Related articles">
          <h2 class="help-article__section-title">Related articles</h2>
          <div class="help-article__related">
            <RouterLink
              v-for="rel in related"
              :key="rel.slug"
              class="help-article__related-item"
              :to="{ name: 'help-article', params: { slug: rel.slug } }"
            >
              <span class="help-article__related-title">{{ rel.title }}</span>
              <span class="help-article__related-desc">{{ rel.description }}</span>
            </RouterLink>
          </div>
        </section>

        <section class="help-article__helpful" aria-label="Was this helpful?">
          <span>Was this helpful?</span>
          <div class="help-article__helpful-actions">
            <VipButton size="sm" variant="secondary" @click="markHelpful(true)">Yes</VipButton>
            <VipButton size="sm" variant="tertiary" @click="markHelpful(false)">No</VipButton>
          </div>
        </section>
      </article>
    </template>

    <VipEmptyState
      v-else
      title="Article not found"
      description="This help article may have moved. Return to Help & Docs to find what you need."
    >
      <template #actions>
        <VipButton variant="primary" @click="router.push({ name: 'help' })">Back to Help &amp; Docs</VipButton>
      </template>
    </VipEmptyState>
  </div>
</template>

<style scoped>
.help-article {
  max-width: 820px;
  margin: 0 auto;
  padding: var(--vip-sp-6);
}
.help-article__breadcrumb {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--vip-sp-2);
  font-size: var(--vip-fs-sm);
  color: var(--vip-text-muted);
  margin-bottom: var(--vip-sp-5);
}
.help-article__breadcrumb a {
  color: var(--vip-brand-text, var(--vip-brand-500));
  text-decoration: none;
}
.help-article__breadcrumb a:hover {
  text-decoration: underline;
}
.help-article__crumb-current {
  color: var(--vip-text-secondary);
}
.help-article__title {
  font-size: var(--vip-fs-2xl, 1.75rem);
  font-weight: var(--vip-fw-semibold);
}
.help-article__desc {
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-2);
}
.help-article__body {
  margin-top: var(--vip-sp-5);
}
.help-article__para {
  color: var(--vip-text-secondary);
  line-height: 1.7;
}
.help-article__para + .help-article__para {
  margin-top: var(--vip-sp-4);
}
.help-article__subhead {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
  margin: var(--vip-sp-5) 0 var(--vip-sp-3);
}
.help-article__steps,
.help-article__list {
  margin: var(--vip-sp-2) 0;
  padding-left: var(--vip-sp-6);
  color: var(--vip-text-secondary);
  line-height: 1.7;
}
.help-article__steps li,
.help-article__list li {
  margin: var(--vip-sp-2) 0;
}
.help-article__note {
  margin-top: var(--vip-sp-5);
  padding: var(--vip-sp-4);
  border-left: 3px solid var(--vip-brand-500);
  background: var(--vip-surface-2);
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
.help-article__section {
  margin-top: var(--vip-sp-7);
}
.help-article__section-title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-4);
}
.help-article__related {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--vip-sp-4);
}
.help-article__related-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--vip-sp-4);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  text-decoration: none;
}
.help-article__related-item:hover {
  border-color: var(--vip-brand-500);
  background: var(--vip-surface-2);
}
.help-article__related-title {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-sm);
}
.help-article__related-desc {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
}
.help-article__helpful {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  margin-top: var(--vip-sp-7);
  padding-top: var(--vip-sp-5);
  border-top: 1px solid var(--vip-border-subtle);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
}
.help-article__helpful-actions {
  display: flex;
  gap: var(--vip-sp-2);
}
@media (max-width: 600px) {
  .help-article {
    padding: var(--vip-sp-4);
  }
}
</style>
