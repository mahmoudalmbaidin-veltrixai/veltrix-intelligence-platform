<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { HELP_CATEGORIES, HELP_FAQ, POPULAR_GUIDES, articlesByCategory, searchHelp } from './content'
import HelpSupportSection from './HelpSupportSection.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipInput from '@/shared/ui/VipInput.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'

const query = ref('')
const results = computed(() => searchHelp(query.value))
const searching = computed(() => query.value.trim().length > 0)

const troubleshooting = computed(() => articlesByCategory('troubleshooting'))
const openFaq = ref<string | null>(null)
function toggleFaq(id: string) {
  openFaq.value = openFaq.value === id ? null : id
}
</script>

<template>
  <div class="help">
    <header class="help__header">
      <h1 class="help__title">Help &amp; Documentation</h1>
      <p class="help__subtitle">Find answers, learn the platform, and get help when you need it.</p>
      <div class="help__search">
        <VipIcon name="search" :size="18" class="help__search-icon" />
        <VipInput
          v-model="query"
          type="search"
          aria-label="Search help articles, guides, and FAQs"
          placeholder="Search help articles, guides, and FAQs..."
        />
      </div>
    </header>

    <!-- ===================== SEARCH RESULTS ===================== -->
    <section v-if="searching" class="help__section" aria-label="Search results">
      <template v-if="results.length">
        <p class="help__results-count">{{ results.length }} result{{ results.length === 1 ? '' : 's' }}</p>
        <ul class="help__results">
          <li
            v-for="result in results"
            :key="result.type + '-' + (result.type === 'article' ? result.slug : result.id)"
          >
            <RouterLink
              v-if="result.type === 'article'"
              class="help__result"
              :to="{ name: 'help-article', params: { slug: result.slug } }"
            >
              <div class="help__result-main">
                <span class="help__result-title">{{ result.title }}</span>
                <span class="help__result-desc">{{ result.description }}</span>
              </div>
              <VipBadge tone="neutral" size="sm" variant="soft">Article</VipBadge>
            </RouterLink>
            <RouterLink v-else class="help__result" :to="{ name: 'help', hash: '#faq' }">
              <div class="help__result-main">
                <span class="help__result-title">{{ result.title }}</span>
                <span class="help__result-desc">{{ result.description }}</span>
              </div>
              <VipBadge tone="neutral" size="sm" variant="soft">FAQ</VipBadge>
            </RouterLink>
          </li>
        </ul>
      </template>
      <VipCard v-else class="help__empty">
        <p class="help__empty-title">No results found for “{{ query }}”</p>
        <p class="help__empty-hint">Try searching for connections, pipelines, dashboards, exports, or users.</p>
      </VipCard>
    </section>

    <!-- ===================== BROWSE ===================== -->
    <template v-else>
      <!-- Popular guides -->
      <section class="help__section" aria-label="Popular guides">
        <h2 class="help__section-title">Popular Guides</h2>
        <div class="help__cards">
          <RouterLink
            v-for="guide in POPULAR_GUIDES"
            :key="guide.slug"
            class="help__card"
            :to="{ name: 'help-article', params: { slug: guide.slug } }"
          >
            <span class="help__card-icon"><VipIcon :name="guide.icon" :size="20" /></span>
            <span class="help__card-title">{{ guide.title }}</span>
            <span class="help__card-desc">{{ guide.description }}</span>
          </RouterLink>
        </div>
      </section>

      <!-- Categories -->
      <section
        v-for="category in HELP_CATEGORIES"
        :key="category.key"
        class="help__section"
        :aria-label="category.label"
      >
        <div class="help__section-head">
          <h2 class="help__section-title">{{ category.label }}</h2>
          <span class="help__section-desc">{{ category.description }}</span>
        </div>
        <VipCard :padded="false">
          <ul class="help__list">
            <li v-for="article in articlesByCategory(category.key)" :key="article.slug">
              <RouterLink class="help__list-item" :to="{ name: 'help-article', params: { slug: article.slug } }">
                <span class="help__list-title">{{ article.title }}</span>
                <span class="help__list-desc">{{ article.description }}</span>
              </RouterLink>
            </li>
          </ul>
        </VipCard>
      </section>

      <!-- FAQ -->
      <section id="faq" class="help__section" aria-label="Frequently asked questions">
        <h2 class="help__section-title">Frequently Asked Questions</h2>
        <VipCard :padded="false">
          <ul class="help__faq">
            <li v-for="faq in HELP_FAQ" :key="faq.id" class="help__faq-item">
              <button
                type="button"
                class="help__faq-q"
                :aria-expanded="openFaq === faq.id"
                :aria-controls="'faq-' + faq.id"
                @click="toggleFaq(faq.id)"
              >
                <span>{{ faq.question }}</span>
                <VipIcon :name="openFaq === faq.id ? 'chevronDown' : 'chevronRight'" :size="16" />
              </button>
              <p v-show="openFaq === faq.id" :id="'faq-' + faq.id" class="help__faq-a" role="region">
                {{ faq.answer }}
              </p>
            </li>
          </ul>
        </VipCard>
      </section>

      <!-- Troubleshooting quick links -->
      <section class="help__section" aria-label="Troubleshooting">
        <h2 class="help__section-title">Troubleshooting</h2>
        <div class="help__trouble">
          <RouterLink
            v-for="item in troubleshooting"
            :key="item.slug"
            class="help__trouble-item"
            :to="{ name: 'help-article', params: { slug: item.slug } }"
          >
            <VipIcon name="warning" :size="15" />
            <span>{{ item.title }}</span>
          </RouterLink>
        </div>
      </section>
    </template>

    <!-- Support -->
    <section class="help__section">
      <HelpSupportSection />
    </section>
  </div>
</template>

<style scoped>
.help {
  max-width: 1000px;
  margin: 0 auto;
  padding: var(--vip-sp-6);
}
.help__header {
  text-align: center;
  padding: var(--vip-sp-4) 0 var(--vip-sp-6);
}
.help__title {
  font-size: var(--vip-fs-2xl, 1.9rem);
  font-weight: var(--vip-fw-semibold);
}
.help__subtitle {
  color: var(--vip-text-muted);
  margin-top: var(--vip-sp-2);
}
.help__search {
  position: relative;
  max-width: 560px;
  margin: var(--vip-sp-5) auto 0;
  text-align: left;
}
.help__search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--vip-text-muted);
  pointer-events: none;
  z-index: 1;
}
.help__search :deep(input) {
  padding-left: 38px;
}
.help__section {
  margin-top: var(--vip-sp-7);
}
.help__section-head {
  display: flex;
  align-items: baseline;
  gap: var(--vip-sp-3);
  flex-wrap: wrap;
  margin-bottom: var(--vip-sp-4);
}
.help__section-title {
  font-size: var(--vip-fs-lg);
  font-weight: var(--vip-fw-semibold);
  margin-bottom: var(--vip-sp-4);
}
.help__section-head .help__section-title {
  margin-bottom: 0;
}
.help__section-desc {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
}
/* Popular guide cards */
.help__cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--vip-sp-4);
}
.help__card {
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
  padding: var(--vip-sp-5);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg, 12px);
  background: var(--vip-surface-1);
  text-decoration: none;
  transition:
    border-color 120ms ease,
    transform 120ms ease;
}
.help__card:hover {
  border-color: var(--vip-brand-500);
  transform: translateY(-1px);
}
.help__card-icon {
  display: inline-flex;
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
  border-radius: var(--vip-radius-md);
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text, var(--vip-brand-500));
  margin-bottom: var(--vip-sp-2);
}
.help__card-title {
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.help__card-desc {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  line-height: 1.5;
}
/* Category lists */
.help__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.help__list-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: var(--vip-sp-4) var(--vip-sp-5);
  border-bottom: 1px solid var(--vip-border-subtle);
  text-decoration: none;
}
.help__list li:last-child .help__list-item {
  border-bottom: none;
}
.help__list-item:hover {
  background: var(--vip-surface-2);
}
.help__list-title {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-sm);
}
.help__list-desc {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
}
/* FAQ */
.help__faq {
  list-style: none;
  margin: 0;
  padding: 0;
}
.help__faq-item {
  border-bottom: 1px solid var(--vip-border-subtle);
}
.help__faq-item:last-child {
  border-bottom: none;
}
.help__faq-q {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4) var(--vip-sp-5);
  background: none;
  border: none;
  font: inherit;
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
  text-align: left;
  cursor: pointer;
}
.help__faq-q:hover {
  background: var(--vip-surface-2);
}
.help__faq-a {
  padding: 0 var(--vip-sp-5) var(--vip-sp-4);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
  line-height: 1.6;
}
/* Troubleshooting */
.help__trouble {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--vip-sp-3);
}
.help__trouble-item {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-3);
  padding: var(--vip-sp-3) var(--vip-sp-4);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  font-size: var(--vip-fs-sm);
  text-decoration: none;
}
.help__trouble-item:hover {
  border-color: var(--vip-brand-500);
  color: var(--vip-text-primary);
}
/* Search results */
.help__results-count {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  margin-bottom: var(--vip-sp-3);
}
.help__results {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--vip-sp-2);
}
.help__result {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vip-sp-4);
  padding: var(--vip-sp-4);
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md);
  text-decoration: none;
}
.help__result:hover {
  border-color: var(--vip-brand-500);
  background: var(--vip-surface-2);
}
.help__result-main {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.help__result-title {
  font-weight: var(--vip-fw-medium);
  color: var(--vip-text-primary);
  font-size: var(--vip-fs-sm);
}
.help__result-desc {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.help__empty {
  text-align: center;
}
.help__empty-title {
  font-weight: var(--vip-fw-medium);
}
.help__empty-hint {
  color: var(--vip-text-muted);
  font-size: var(--vip-fs-sm);
  margin-top: var(--vip-sp-2);
}
@media (max-width: 600px) {
  .help {
    padding: var(--vip-sp-4);
  }
}
</style>
