import { describe, expect, it } from 'vitest'

import { formatKpi } from './formatKpi'

describe('formatKpi', () => {
  it('reads a rate as a percentage', () => {
    expect(formatKpi({ id: 'escalation_rate', label: 'Escalation rate', value: 20, format: 'percent' })).toBe('20%')
  })

  it('reads a duration in minutes and seconds', () => {
    expect(formatKpi({ id: 'avg_duration', label: 'Avg duration', value: 303, format: 'duration' })).toBe('5m 03s')
  })

  it('groups a plain count so a four-figure number stays readable', () => {
    expect(formatKpi({ id: 'total', label: 'Total conversations', value: 4812, format: 'number' })).toBe('4,812')
  })

  it('treats an unspecified format as a plain count', () => {
    expect(formatKpi({ id: 'calls', label: 'Calls answered', value: 41 })).toBe('41')
  })

  it('renders a zero rate as 0%, not as an absent value', () => {
    expect(formatKpi({ id: 'escalation_rate', label: 'Escalation rate', value: 0, format: 'percent' })).toBe('0%')
  })
})
