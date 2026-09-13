/**
 * WCAG 2.1 contrast ratio between two sRGB hex colors
 * (https://www.w3.org/TR/WCAG21/#dfn-relative-luminance). Returns a value
 * from 1 (identical colors) to 21 (black against white). Argument order
 * doesn't matter — the formula always compares the lighter color to the
 * darker one.
 */
export function contrastRatio(hexA: string, hexB: string): number {
  const luminanceA = relativeLuminance(hexA)
  const luminanceB = relativeLuminance(hexB)
  const lighter = Math.max(luminanceA, luminanceB)
  const darker = Math.min(luminanceA, luminanceB)
  return (lighter + 0.05) / (darker + 0.05)
}

function relativeLuminance(hex: string): number {
  const [r, g, b] = toRgb(hex).map(toLinear)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function toRgb(hex: string): [number, number, number] {
  const normalized = hex.replace('#', '')
  return [
    parseInt(normalized.slice(0, 2), 16),
    parseInt(normalized.slice(2, 4), 16),
    parseInt(normalized.slice(4, 6), 16),
  ]
}

function toLinear(channel: number): number {
  const c = channel / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}
