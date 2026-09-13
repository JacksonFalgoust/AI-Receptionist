import { cn } from '@/lib/cn'
import type { UsageMetric } from '@/types'

const WARNING_AT = 80
const OVER_AT = 100

/**
 * Whole percent of the allowance used, or null when the plan includes no
 * allowance to measure against — dividing by zero would otherwise render
 * "Infinity%".
 *
 * Floored rather than rounded, and the tone band below is computed from this
 * same floored value so the two can never disagree: rounding would let 99.6%
 * print "100% — approaching your plan limit", a sentence that contradicts its
 * own number. Flooring makes "100%" mean genuinely at or over the allowance.
 */
export function usageShare(metric: UsageMetric): number | null {
  if (metric.included <= 0) return null
  return Math.floor((metric.used / metric.included) * 100)
}

function describeShare(share: number): { text: string; fill: string } {
  if (share >= OVER_AT) {
    return { text: `${share}% — over your plan limit`, fill: 'bg-danger' }
  }
  if (share >= WARNING_AT) {
    return { text: `${share}% — approaching your plan limit`, fill: 'bg-warning' }
  }
  return { text: `${share}% of plan`, fill: 'bg-brand' }
}

export interface UsageMeterProps {
  metric: UsageMetric
}

/**
 * PRD §21's usage metrics, one metric per meter. `BillingPage` maps the
 * `usage` array over this, so there is no list wrapper.
 *
 * `role="meter"`, not `progressbar`: this is a measurement within a known
 * range, not the progress of a task. The state is always in words as well as
 * in the bar's colour — nothing here reads by colour alone (US-14.2).
 */
export function UsageMeter({ metric }: UsageMeterProps) {
  const share = usageShare(metric)
  const used = metric.used.toLocaleString('en-US')

  if (share === null) {
    return (
      <div className="border-b border-border py-3 last:border-0">
        <div className="flex items-baseline justify-between gap-4">
          <span className="text-sm font-medium text-ink">{metric.label}</span>
          <span className="text-sm text-ink-secondary">{`${used} ${metric.unit} used`}</span>
        </div>
      </div>
    )
  }

  const { text, fill } = describeShare(share)

  return (
    <div className="border-b border-border py-3 last:border-0">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-medium text-ink">{metric.label}</span>
        <span className="text-sm text-ink-secondary">
          {`${used} of ${metric.included.toLocaleString('en-US')}`}
        </span>
      </div>
      <div
        role="meter"
        aria-label={metric.label}
        aria-valuenow={metric.used}
        aria-valuemin={0}
        aria-valuemax={metric.included}
        aria-valuetext={text}
        className="mt-2 h-2 w-full overflow-hidden rounded-full bg-canvas-tint"
      >
        <div
          // Capped at 100% so an over-limit bar fills rather than overflowing
          // its track; the words carry the real figure.
          style={{ width: `${Math.min(share, 100)}%` }}
          className={cn('h-full rounded-full', fill)}
        />
      </div>
      <p className="mt-1 text-xs text-ink-muted">{text}</p>
    </div>
  )
}
