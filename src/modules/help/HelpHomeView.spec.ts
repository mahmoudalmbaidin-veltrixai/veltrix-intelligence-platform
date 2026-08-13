import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import HelpHomeView from './HelpHomeView.vue'

const RouterLinkStub = {
  props: ['to'],
  template: '<a class="rl"><slot /></a>',
}

function mountHome() {
  return mount(HelpHomeView, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        // The support section depends on platform/router stores; not under test here.
        HelpSupportSection: true,
      },
    },
  })
}

describe('HelpHomeView', () => {
  it('renders the header, search, popular guides and FAQ by default', () => {
    const wrapper = mountHome()
    expect(wrapper.text()).toContain('Help & Documentation')
    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Popular Guides')
    // Four popular guide cards.
    expect(wrapper.findAll('.help__card')).toHaveLength(4)
    // FAQ accordion questions rendered as buttons.
    expect(wrapper.findAll('.help__faq-q').length).toBeGreaterThanOrEqual(10)
  })

  it('filters to search results and hides browse sections when searching', async () => {
    const wrapper = mountHome()
    await wrapper.find('input[type="search"]').setValue('export pdf')
    expect(wrapper.find('.help__results').exists()).toBe(true)
    expect(wrapper.text().toLowerCase()).toContain('pdf')
    // Browse sections are replaced by results.
    expect(wrapper.find('.help__cards').exists()).toBe(false)
  })

  it('shows a helpful empty state for a non-matching query', async () => {
    const wrapper = mountHome()
    await wrapper.find('input[type="search"]').setValue('zzzznotarealterm')
    expect(wrapper.text()).toContain('No results found')
    expect(wrapper.text()).toContain('Try searching for connections, pipelines, dashboards')
  })

  it('opens and closes an FAQ answer via its accessible button', async () => {
    const wrapper = mountHome()
    const first = wrapper.find('.help__faq-q')
    expect(first.attributes('aria-expanded')).toBe('false')
    await first.trigger('click')
    expect(first.attributes('aria-expanded')).toBe('true')
    await first.trigger('click')
    expect(first.attributes('aria-expanded')).toBe('false')
  })
})
