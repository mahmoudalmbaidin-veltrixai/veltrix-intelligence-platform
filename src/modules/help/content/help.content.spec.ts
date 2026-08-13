import { describe, expect, it } from 'vitest'
import { HELP_ARTICLES, HELP_FAQ, POPULAR_GUIDES, articlesByCategory, getArticle, searchHelp } from './index'

describe('help content model', () => {
  it('ships the expected MVP content volume', () => {
    expect(POPULAR_GUIDES).toHaveLength(4)
    expect(articlesByCategory('getting-started')).toHaveLength(7)
    expect(articlesByCategory('quick-guides')).toHaveLength(10)
    expect(articlesByCategory('troubleshooting').length).toBeGreaterThanOrEqual(10)
    expect(HELP_FAQ.length).toBeGreaterThanOrEqual(10)
    expect(HELP_FAQ.length).toBeLessThanOrEqual(15)
  })

  it('exposes unique article slugs resolvable by getArticle', () => {
    const slugs = HELP_ARTICLES.map((a) => a.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
    for (const slug of slugs) expect(getArticle(slug)?.slug).toBe(slug)
  })

  it('every popular guide points to a real article', () => {
    for (const guide of POPULAR_GUIDES) expect(getArticle(guide.slug)).toBeTruthy()
  })

  it('every related-article reference resolves', () => {
    for (const article of HELP_ARTICLES) {
      for (const rel of article.related ?? []) expect(getArticle(rel)).toBeTruthy()
    }
  })
})

describe('help search', () => {
  it('matches by keyword, title, and phrase', () => {
    expect(searchHelp('pipeline').some((r) => r.type === 'article')).toBe(true)
    expect(searchHelp('upload excel').some((r) => r.title.toLowerCase().includes('csv or excel'))).toBe(true)
    expect(searchHelp('export pdf').some((r) => r.title.toLowerCase().includes('pdf'))).toBe(true)
    expect(searchHelp('connection failed').length).toBeGreaterThan(0)
    expect(searchHelp('invite user').some((r) => r.title.toLowerCase().includes('invite'))).toBe(true)
  })

  it('includes FAQ entries in results', () => {
    const results = searchHelp('organization workspace')
    expect(results.some((r) => r.type === 'faq')).toBe(true)
  })

  it('returns nothing for an empty or non-matching query', () => {
    expect(searchHelp('')).toEqual([])
    expect(searchHelp('   ')).toEqual([])
    expect(searchHelp('zzzznotarealterm')).toEqual([])
  })

  it('ranks a title match above a body-only match', () => {
    const results = searchHelp('pipeline')
    expect(results[0]?.type).toBe('article')
    // The first result should be a pipeline-titled article, not an incidental mention.
    if (results[0]?.type === 'article') {
      expect(results[0].title.toLowerCase()).toContain('pipeline')
    }
  })
})
