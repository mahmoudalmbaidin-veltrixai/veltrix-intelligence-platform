import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VipCombobox from './VipCombobox.vue'

// A representative slice of the IANA set plus a large synthetic tail to prove
// the menu never renders the whole universe of options at once.
const TZ = [
  { value: 'Asia/Riyadh', label: 'Asia/Riyadh' },
  { value: 'Asia/Amman', label: 'Asia/Amman' },
  { value: 'Europe/London', label: 'Europe/London' },
  { value: 'America/New_York', label: 'America/New York' },
]
const bulk = Array.from({ length: 500 }, (_, i) => ({ value: `Etc/Zone_${i}`, label: `Etc/Zone ${i}` }))
const OPTIONS = [...TZ, ...bulk]

const mountBox = (modelValue = 'Asia/Riyadh', maxResults = 50) =>
  mount(VipCombobox, {
    props: { modelValue, options: OPTIONS, label: 'Time zone', maxResults },
    attachTo: document.body,
  })

const input = (w: ReturnType<typeof mountBox>) => w.find('input[role="combobox"]')
const optionTexts = (w: ReturnType<typeof mountBox>) => w.findAll('[role="option"]').map((o) => o.text())

describe('VipCombobox (CERT-P2-001 timezone selector)', () => {
  it('Test 1 & 8 — shows the saved value and keeps it visible/selected when opened', async () => {
    const w = mountBox('Asia/Riyadh')
    // Closed: the input displays the current selection's label.
    expect((input(w).element as HTMLInputElement).value).toBe('Asia/Riyadh')
    // Open with no query: the selected option is present and marked selected,
    // even though it would fall outside the capped head of a 504-item list.
    await input(w).trigger('focus')
    const selected = w.find('[role="option"][aria-selected="true"]')
    expect(selected.exists()).toBe(true)
    expect(selected.text()).toContain('Asia/Riyadh')
  })

  it('Test 2 — search finds a timezone by city and by region prefix', async () => {
    const w = mountBox()
    await input(w).trigger('focus')
    await input(w).setValue('Riyadh')
    expect(optionTexts(w).some((t) => t.includes('Asia/Riyadh'))).toBe(true)

    await input(w).setValue('new york') // matches America/New_York (underscore folded)
    expect(optionTexts(w).some((t) => t.includes('America/New York'))).toBe(true)

    await input(w).setValue('Europe/') // region prefix
    const texts = optionTexts(w)
    expect(texts.some((t) => t.includes('Europe/London'))).toBe(true)
    expect(texts.some((t) => t.includes('Asia/Riyadh'))).toBe(false)
  })

  it('Test 3 & 4 — selecting a result emits the canonical IANA value', async () => {
    const w = mountBox('UTC')
    await input(w).trigger('focus')
    await input(w).setValue('Amman')
    const opt = w.findAll('[role="option"]').find((o) => o.text().includes('Asia/Amman'))!
    await opt.trigger('click')
    // Canonical value, not the display label.
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual(['Asia/Amman'])
    // Menu closes after selection.
    expect(w.findAll('[role="option"]').length).toBe(0)
  })

  it('performance — never renders more than maxResults options at once', async () => {
    const w = mountBox('Asia/Riyadh', 50)
    await input(w).trigger('focus')
    // 504 options exist, but the rendered list is capped.
    expect(w.findAll('[role="option"]').length).toBeLessThanOrEqual(50)
    // A truncation hint tells the user to keep typing.
    expect(w.find('.vip-combobox__more').exists()).toBe(true)
  })

  it('keyboard — arrow + Enter selects; Escape closes without changing value', async () => {
    const w = mountBox('UTC')
    await input(w).trigger('focus')
    await input(w).setValue('Asia/')
    await input(w).trigger('keydown', { key: 'ArrowDown' })
    await input(w).trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue')).toBeTruthy()

    const w2 = mountBox('Asia/Riyadh')
    await input(w2).trigger('focus')
    await input(w2).trigger('keydown', { key: 'Escape' })
    expect(w2.findAll('[role="option"]').length).toBe(0)
    expect(w2.emitted('update:modelValue')).toBeFalsy()
  })

  it('accessibility — exposes combobox/listbox roles and active-descendant', async () => {
    const w = mountBox('Asia/Riyadh')
    const el = input(w)
    expect(el.attributes('role')).toBe('combobox')
    expect(el.attributes('aria-expanded')).toBe('false')
    expect(el.attributes('aria-autocomplete')).toBe('list')
    await el.trigger('focus')
    expect(el.attributes('aria-expanded')).toBe('true')
    expect(w.find('[role="listbox"]').exists()).toBe(true)
    expect(el.attributes('aria-activedescendant')).toBeTruthy()
  })

  it('Test 7 — falls back to showing the raw model value even if unmatched by label', async () => {
    // A saved zone with no matching option must still display (not vanish).
    const w = mountBox('Pacific/Chatham')
    expect((input(w).element as HTMLInputElement).value).toBe('Pacific/Chatham')
  })
})
