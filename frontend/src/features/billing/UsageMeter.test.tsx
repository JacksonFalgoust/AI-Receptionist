import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { UsageMetric } from '@/types'

import { UsageMeter, usageShare } from './UsageMeter'

function metric(used: number, included: number): UsageMetric {
  return { id: 'usage_voice', label: 'Voice minutes', used, included, unit: 'minutes' }
}

describe('usageShare', () => {
  it('floors the percentage so it can never overstate usage', () => {
    expect(usageShare(metric(9960, 10000))).toBe(99)
  })

  it('reports at or over the allowance exactly', () => {
    expect(usageShare(metric(10400, 10000))).toBe(104)
  })

  it('has no share to report without an allowance', () => {
    expect(usageShare(metric(120, 0))).toBeNull()
  })
})

describe('UsageMeter', () => {
  it('exposes the measurement to assistive technology', () => {
    render(<UsageMeter metric={metric(9600, 12000)} />)

    const meter = screen.getByRole('meter', { name: /voice minutes/i })
    expect(meter).toHaveAttribute('aria-valuenow', '9600')
    expect(meter).toHaveAttribute('aria-valuemin', '0')
    expect(meter).toHaveAttribute('aria-valuemax', '12000')
  })

  it('shows the exact figures alongside the bar', () => {
    render(<UsageMeter metric={metric(9600, 12000)} />)
    expect(screen.getByText('9,600 of 12,000')).toBeInTheDocument()
  })

  it('says nothing extra below the warning threshold', () => {
    render(<UsageMeter metric={metric(1840, 3000)} />)
    expect(screen.getByText('61% of plan')).toBeInTheDocument()
  })

  // Status is never carried by the bar's colour alone (WCAG 2.1 AA, US-14.2).
  it('warns in words when approaching the limit', () => {
    render(<UsageMeter metric={metric(9600, 12000)} />)
    expect(screen.getByText('80% — approaching your plan limit')).toBeInTheDocument()
  })

  it('says so in words when over the limit', () => {
    render(<UsageMeter metric={metric(12400, 12000)} />)
    expect(screen.getByText('103% — over your plan limit')).toBeInTheDocument()
  })

  it('renders the used figure with no bar when the plan includes no allowance', () => {
    render(<UsageMeter metric={metric(120, 0)} />)

    expect(screen.getByText('120 minutes used')).toBeInTheDocument()
    expect(screen.queryByRole('meter')).not.toBeInTheDocument()
  })
})
