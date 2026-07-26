import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VipConfirmDialog from './VipConfirmDialog.vue'

// Teleport renders to <body>; stub it so content stays inline for querying.
const mountOpen = (props: Record<string, unknown>) =>
  mount(VipConfirmDialog, {
    props: { open: true, title: 'Archive dashboard?', ...props },
    global: { stubs: { teleport: true } },
  })

function confirmButton(wrapper: ReturnType<typeof mountOpen>) {
  return wrapper.findAll('button').find((b) => /Archive|Delete|Restore|Disable/.test(b.text()))!
}

describe('VipConfirmDialog', () => {
  it('renders title, message and impact when open', () => {
    const w = mountOpen({
      message: 'This will be removed from active lists.',
      resourceName: 'Executive Overview',
      impact: ['3 pages', 'Published'],
    })
    expect(w.text()).toContain('This will be removed from active lists.')
    expect(w.text()).toContain('Executive Overview')
    expect(w.text()).toContain('3 pages')
  })

  it('emits confirm for a non-typed action', async () => {
    const w = mountOpen({ level: 'warning', confirmLabel: 'Archive' })
    await confirmButton(w).trigger('click')
    expect(w.emitted('confirm')).toBeTruthy()
  })

  it('gates confirm behind typed confirmation for destructive actions', async () => {
    const w = mountOpen({
      level: 'danger',
      confirmLabel: 'Delete',
      resourceName: 'Sales Pipeline',
      requireTyping: true,
    })
    // Disabled until the typed value matches the resource name.
    expect(confirmButton(w).attributes('disabled')).toBeDefined()
    await confirmButton(w).trigger('click')
    expect(w.emitted('confirm')).toBeFalsy()

    await w.find('#vip-confirm-typed').setValue('Sales Pipeline')
    expect(confirmButton(w).attributes('disabled')).toBeUndefined()
    await confirmButton(w).trigger('click')
    expect(w.emitted('confirm')).toBeTruthy()
  })

  it('does not emit confirm while pending and shows the backend error', () => {
    const w = mountOpen({
      level: 'danger',
      confirmLabel: 'Delete',
      pending: true,
      error: 'This dashboard has active delivery schedules. (CONFLICT)',
    })
    expect(confirmButton(w).attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('This dashboard has active delivery schedules.')
  })

  it('emits cancel from the cancel button', async () => {
    const w = mountOpen({})
    const cancel = w.findAll('button').find((b) => b.text() === 'Cancel')!
    await cancel.trigger('click')
    expect(w.emitted('cancel')).toBeTruthy()
  })
})
