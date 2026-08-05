import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MapChart from './MapChart.vue'

describe('MapChart', () => {
  it('renders geospatial points with accessible labels and clamps invalid coordinates', () => {
    const wrapper = mount(MapChart, {
      props: {
        points: [
          { x: 46.6753, y: 24.7136, size: 81, label: 'Riyadh / الرياض' },
          { x: 500, y: -500, size: 4, label: 'Clamped' },
        ],
      },
    })

    const svg = wrapper.get('svg[role="img"]')
    expect(svg.attributes('aria-label')).toBe('Geospatial data map')
    const points = wrapper.findAll('circle.map__point')
    expect(points).toHaveLength(2)
    expect(points[0]?.text()).toContain('Riyadh / الرياض')
    expect(Number(points[0]?.attributes('cx'))).toBeGreaterThan(320)
    expect(Number(points[0]?.attributes('cy'))).toBeLessThan(150)
    expect(Number(points[1]?.attributes('cx'))).toBe(620)
    expect(Number(points[1]?.attributes('cy'))).toBe(280)
  })
})
