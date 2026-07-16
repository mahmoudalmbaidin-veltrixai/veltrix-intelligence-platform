/** Persisted, pointer-driven panel resizing for studio layouts. */
import { ref, watch, type Ref } from 'vue'
import { LocalStore } from '@/shared/lib/mock'

export interface ResizableOptions {
  key: string
  initial: number
  min: number
  max: number
  /** 'x' shrinks/grows horizontally (default), 'y' vertically. */
  axis?: 'x' | 'y'
  /** Which edge the handle sits on relative to the panel. */
  invert?: boolean
}

export function useResizable(opts: ResizableOptions): {
  size: Ref<number>
  startResize: (e: PointerEvent) => void
  setSize: (n: number) => void
} {
  const store = new LocalStore<{ size: number }>(`vip.panel.${opts.key}`)
  const size = ref(store.read({ size: opts.initial }).size)

  watch(size, (v) => store.write({ size: v }))

  function clamp(v: number) {
    return Math.min(opts.max, Math.max(opts.min, v))
  }
  function setSize(n: number) {
    size.value = clamp(n)
  }

  function startResize(e: PointerEvent) {
    e.preventDefault()
    const start = opts.axis === 'y' ? e.clientY : e.clientX
    const startSize = size.value
    const dir = opts.invert ? -1 : 1

    function onMove(ev: PointerEvent) {
      const current = opts.axis === 'y' ? ev.clientY : ev.clientX
      size.value = clamp(startSize + (current - start) * dir)
    }
    function onUp() {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
    document.body.style.userSelect = 'none'
    document.body.style.cursor = opts.axis === 'y' ? 'row-resize' : 'col-resize'
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return { size, startResize, setSize }
}
