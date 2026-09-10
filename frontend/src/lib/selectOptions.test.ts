import { describe, expect, it } from 'vitest'

import { withCurrentValue, withCurrentValues } from './selectOptions'

const options = [
  { value: 'a', label: 'Option A' },
  { value: 'b', label: 'Option B' },
]

describe('withCurrentValue', () => {
  it('returns the list unchanged when the value is already an option', () => {
    expect(withCurrentValue(options, 'a')).toEqual(options)
  })

  it('returns the list unchanged when the value is blank', () => {
    expect(withCurrentValue(options, '')).toEqual(options)
  })

  it('appends the value as its own option when it matches nothing in the list', () => {
    const result = withCurrentValue(options, 'Legacy Value')
    expect(result).toEqual([...options, { value: 'Legacy Value', label: 'Legacy Value' }])
  })
})

describe('withCurrentValues', () => {
  it('returns the list unchanged when every value is already an option', () => {
    expect(withCurrentValues(options, ['a', 'b'])).toEqual(options)
  })

  it('appends only the values missing from the list, each as its own option', () => {
    const result = withCurrentValues(options, ['a', 'legacy-1', 'legacy-2'])
    expect(result).toEqual([
      ...options,
      { value: 'legacy-1', label: 'legacy-1' },
      { value: 'legacy-2', label: 'legacy-2' },
    ])
  })

  it('never appends the same missing value twice', () => {
    const result = withCurrentValues(options, ['legacy', 'legacy'])
    expect(result.filter((option) => option.value === 'legacy')).toHaveLength(1)
  })
})
