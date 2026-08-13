import { HELP_ARTICLES } from './articles'
import { HELP_FAQ } from './faq'
import type { ArticleBlock, HelpArticle, HelpCategory, HelpCategoryKey, PopularGuide, SearchResult } from './types'

export type {
  ArticleBlock,
  FaqItem,
  HelpArticle,
  HelpCategory,
  HelpCategoryKey,
  PopularGuide,
  SearchResult,
} from './types'
export { HELP_ARTICLES } from './articles'
export { HELP_FAQ } from './faq'

export const HELP_CATEGORIES: HelpCategory[] = [
  {
    key: 'getting-started',
    label: 'Getting Started',
    description: 'Connect → Dataset → Pipeline → Dashboard → Publish.',
    icon: 'sparkles',
  },
  {
    key: 'quick-guides',
    label: 'Quick Guides',
    description: 'Short, action-oriented walkthroughs of common tasks.',
    icon: 'book',
  },
  {
    key: 'troubleshooting',
    label: 'Troubleshooting',
    description: 'Fix common connection, dataset, pipeline, and dashboard issues.',
    icon: 'warning',
  },
]

export const POPULAR_GUIDES: PopularGuide[] = [
  {
    slug: 'connect-a-data-source',
    title: 'Connect Your Data',
    description: 'Learn how to create connections and bring data into VIP.',
    icon: 'database',
  },
  {
    slug: 'build-your-first-pipeline',
    title: 'Build Your First Pipeline',
    description: 'Transform, clean, combine, and prepare your data.',
    icon: 'workflow',
  },
  {
    slug: 'create-your-first-dashboard',
    title: 'Create Your First Dashboard',
    description: 'Turn datasets into interactive analytics and visualizations.',
    icon: 'chart',
  },
  {
    slug: 'publish-a-dashboard',
    title: 'Publish & Export',
    description: 'Publish dashboards and export your results in supported formats.',
    icon: 'upload',
  },
]

const ARTICLE_BY_SLUG = new Map(HELP_ARTICLES.map((a) => [a.slug, a]))

export function getArticle(slug: string): HelpArticle | undefined {
  return ARTICLE_BY_SLUG.get(slug)
}

export function articlesByCategory(category: HelpCategoryKey): HelpArticle[] {
  return HELP_ARTICLES.filter((a) => a.category === category)
}

export function categoryLabel(category: HelpCategoryKey): string {
  return HELP_CATEGORIES.find((c) => c.key === category)?.label ?? category
}

export function relatedArticles(article: HelpArticle): HelpArticle[] {
  return (article.related ?? []).map((slug) => ARTICLE_BY_SLUG.get(slug)).filter((a): a is HelpArticle => !!a)
}

function blockText(block: ArticleBlock): string {
  if (block.kind === 'para' || block.kind === 'subhead' || block.kind === 'note') return block.text
  return block.items.join(' ')
}

/** Local, fast search over article titles/descriptions/keywords/body and FAQ. */
export function searchHelp(query: string): SearchResult[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  const terms = q.split(/\s+/).filter(Boolean)

  const scoreText = (haystack: string, weight: number): number => {
    const text = haystack.toLowerCase()
    return terms.reduce((score, term) => (text.includes(term) ? score + weight : score), 0)
  }

  const results: { score: number; result: SearchResult }[] = []

  for (const article of HELP_ARTICLES) {
    const body = article.body.map(blockText).join(' ')
    const score =
      scoreText(article.title, 6) +
      scoreText(article.description, 3) +
      scoreText(article.keywords.join(' '), 4) +
      scoreText(body, 1)
    if (score > 0) {
      results.push({
        score,
        result: {
          type: 'article',
          slug: article.slug,
          title: article.title,
          description: article.description,
          category: article.category,
        },
      })
    }
  }

  for (const faq of HELP_FAQ) {
    const score = scoreText(faq.question, 6) + scoreText(faq.keywords.join(' '), 4) + scoreText(faq.answer, 1)
    if (score > 0) {
      results.push({
        score,
        result: { type: 'faq', id: faq.id, title: faq.question, description: faq.answer },
      })
    }
  }

  return results.sort((a, b) => b.score - a.score).map((r) => r.result)
}
