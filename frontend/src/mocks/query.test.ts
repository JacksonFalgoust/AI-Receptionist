import { beforeEach, describe, expect, it } from 'vitest'

import {
  matchesSearch,
  nextId,
  paginate,
  resetIds,
  sortByDesc,
  withinRange,
} from './query'

describe('paginate', () => {
  const items = Array.from({ length: 12 }, (_, index) => index + 1)

  it('defaults to the first page', () => {
    const result = paginate(items)
    expect(result.page).toBe(1)
    expect(result.total).toBe(12)
    expect(result.items).toHaveLength(12)
  })

  it('slices to the requested page', () => {
    const result = paginate(items, { page: 2, pageSize: 5 })
    expect(result.items).toEqual([6, 7, 8, 9, 10])
    expect(result.page).toBe(2)
    expect(result.pageSize).toBe(5)
    expect(result.total).toBe(12)
  })

  it('returns an empty page past the end without changing the total', () => {
    const result = paginate(items, { page: 9, pageSize: 5 })
    expect(result.items).toEqual([])
    expect(result.total).toBe(12)
  })

  it('clamps a page below 1', () => {
    expect(paginate(items, { page: 0, pageSize: 4 }).items).toEqual([1, 2, 3, 4])
  })
})

describe('matchesSearch', () => {
  it('matches with no search term', () => {
    expect(matchesSearch(['Alex Morgan'], undefined)).toBe(true)
    expect(matchesSearch(['Alex Morgan'], '   ')).toBe(true)
  })

  it('matches case-insensitively on any field', () => {
    expect(matchesSearch(['Alex Morgan', '+1 555 0142'], 'morgan')).toBe(true)
    expect(matchesSearch(['Alex Morgan', '+1 555 0142'], '0142')).toBe(true)
  })

  it('ignores undefined fields and returns false on no match', () => {
    expect(matchesSearch(['Alex Morgan', undefined], 'nobody')).toBe(false)
  })
})

describe('withinRange', () => {
  const at = '2026-09-04T12:00:00.000Z'

  it('accepts when no bounds are given', () => {
    expect(withinRange(at)).toBe(true)
  })

  it('respects the lower bound', () => {
    expect(withinRange(at, '2026-09-05T00:00:00.000Z')).toBe(false)
    expect(withinRange(at, '2026-09-01T00:00:00.000Z')).toBe(true)
  })

  it('respects the upper bound', () => {
    expect(withinRange(at, undefined, '2026-09-03T00:00:00.000Z')).toBe(false)
    expect(withinRange(at, undefined, '2026-09-30T00:00:00.000Z')).toBe(true)
  })
})

describe('sortByDesc', () => {
  it('sorts newest first without mutating the input', () => {
    const input = [
      { at: '2026-09-01T00:00:00.000Z' },
      { at: '2026-09-08T00:00:00.000Z' },
      { at: '2026-09-04T00:00:00.000Z' },
    ]
    const sorted = sortByDesc(input, (item) => item.at)

    expect(sorted.map((item) => item.at)).toEqual([
      '2026-09-08T00:00:00.000Z',
      '2026-09-04T00:00:00.000Z',
      '2026-09-01T00:00:00.000Z',
    ])
    expect(input[0].at).toBe('2026-09-01T00:00:00.000Z')
  })
})

describe('nextId', () => {
  beforeEach(() => {
    resetIds()
  })

  it('produces stable, prefixed, increasing ids', () => {
    expect(nextId('conv')).toBe('conv_0001')
    expect(nextId('conv')).toBe('conv_0002')
  })

  it('restarts after resetIds', () => {
    nextId('conv')
    resetIds()
    expect(nextId('conv')).toBe('conv_0001')
  })
})
