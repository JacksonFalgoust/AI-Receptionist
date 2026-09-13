import { describe, expect, it } from 'vitest'

import { contrastRatio } from './colorContrast'

describe('contrastRatio', () => {
  it('is 21:1 for black on white, WCAG\'s maximum possible ratio', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 0)
  })

  it('is 1:1 for identical colors', () => {
    expect(contrastRatio('#7a8a98', '#7a8a98')).toBeCloseTo(1, 5)
  })

  it('does not depend on argument order', () => {
    expect(contrastRatio('#152028', '#ffffff')).toBeCloseTo(
      contrastRatio('#ffffff', '#152028'),
      10,
    )
  })
})

/**
 * Pins the E5 quality-pass token fixes at WCAG AA's 4.5:1 (normal text).
 * `theme.css`'s CSS custom properties can't be imported into a test, so
 * these hex strings are hand-kept in sync with `src/styles/theme.css` — if
 * you change a value in one file, change it here too. This is what turns
 * the quality-pass audit's one-time finding into a permanent regression
 * guard: a future token edit that drifts back under 4.5:1 fails this test
 * instead of waiting for the next manual audit.
 */
describe('theme token contrast (WCAG AA, 4.5:1)', () => {
  const MIN_AA = 4.5

  it('--color-ink-muted on white (KPI eyebrow labels, muted text)', () => {
    expect(contrastRatio('#5c6a77', '#ffffff')).toBeGreaterThanOrEqual(MIN_AA)
  })

  it('--color-ink-muted on --color-canvas (FilterBar labels)', () => {
    expect(contrastRatio('#5c6a77', '#f3f5f7')).toBeGreaterThanOrEqual(MIN_AA)
  })

  it('--color-ink-muted on --color-canvas-tint (statusTone muted pill, e.g. "Disabled")', () => {
    expect(contrastRatio('#5c6a77', '#e8edf1')).toBeGreaterThanOrEqual(MIN_AA)
  })

  it('--color-rail-text-muted on the nav rail (composited with its 5% white overlay)', () => {
    expect(contrastRatio('#8394a3', '#212b33')).toBeGreaterThanOrEqual(MIN_AA)
  })

  it('--color-success on --color-success-soft (success StatusPill)', () => {
    expect(contrastRatio('#1c7b44', '#e6f6ed')).toBeGreaterThanOrEqual(MIN_AA)
  })

  it('--color-warning on --color-warning-soft (warning StatusPill, e.g. "Degraded")', () => {
    expect(contrastRatio('#966500', '#fff4e0')).toBeGreaterThanOrEqual(MIN_AA)
  })

  it('white text on --color-brand-solid (Button primary, resting)', () => {
    expect(contrastRatio('#ffffff', '#538217')).toBeGreaterThanOrEqual(MIN_AA)
  })

  it('white text on --color-brand-solid-strong (Button primary, hover)', () => {
    expect(contrastRatio('#ffffff', '#487013')).toBeGreaterThanOrEqual(MIN_AA)
  })
})
