/** Structured, maintainable content model for the Help & Docs center. */

export type HelpCategoryKey = 'getting-started' | 'quick-guides' | 'troubleshooting'

/** A block of article content. Kept intentionally small so a single renderer
 * can present guides and troubleshooting articles consistently. */
export type ArticleBlock =
  | { kind: 'para'; text: string }
  | { kind: 'subhead'; text: string }
  | { kind: 'steps'; items: string[] }
  | { kind: 'list'; items: string[] }
  | { kind: 'note'; text: string }

export interface HelpArticle {
  slug: string
  title: string
  description: string
  category: HelpCategoryKey
  keywords: string[]
  body: ArticleBlock[]
  /** Slugs of related articles surfaced at the foot of the article. */
  related?: string[]
}

export interface FaqItem {
  id: string
  question: string
  answer: string
  keywords: string[]
}

export interface HelpCategory {
  key: HelpCategoryKey
  label: string
  description: string
  icon: string
}

export interface PopularGuide {
  slug: string
  title: string
  description: string
  icon: string
}

export type SearchResult =
  | { type: 'article'; slug: string; title: string; description: string; category: HelpCategoryKey }
  | { type: 'faq'; id: string; title: string; description: string }
