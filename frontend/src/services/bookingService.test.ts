import { afterEach, describe, expect, it, vi } from 'vitest'

import { buildBookingFixtures } from '@/mocks/bookings'

import { AppError } from './errors'
import { bookingService, httpBookingService } from './bookingService'
import { http } from './http'

describe('bookingService (mock)', () => {
  it('returns only upcoming bookings, soonest first', async () => {
    const page = await bookingService.list()
    const times = page.items.map((b) => new Date(b.startsAt ?? 0).getTime())

    expect(page.items.length).toBeGreaterThanOrEqual(2)
    expect(page.items.every((b) => b.label === null || b.label === 'out_now' || b.label === 'overdue')).toBe(true)
    expect(times).toEqual([...times].sort((a, b) => a - b))
  })

  it('returns the past bookings for view=past', async () => {
    const page = await bookingService.list({ view: 'past' })
    expect(new Set(page.items.map((b) => b.label))).toEqual(
      new Set(['returned', 'canceled', 'not_picked_up']),
    )
  })

  it('strips the view key and returns the fixture summary', async () => {
    const page = await bookingService.list()
    expect(page.items.every((b) => !('view' in b))).toBe(true)
    expect(page.summary).toEqual(buildBookingFixtures().summary)
  })

  it('paginates without changing the total', async () => {
    const all = await bookingService.list()
    const slice = await bookingService.list({ pageSize: 2, page: 2 })
    expect(slice.total).toBe(all.total)
    expect(slice.items.map((b) => b.id)).toEqual(all.items.slice(2, 4).map((b) => b.id))
  })
})

describe('httpBookingService', () => {
  afterEach(() => vi.restoreAllMocks())

  it('rewrites a server error as a Booqable error', async () => {
    vi.spyOn(http, 'get').mockRejectedValue(
      new AppError({ kind: 'server', title: 'Boom', description: 'x' }),
    )
    await expect(httpBookingService.list()).rejects.toMatchObject({
      title: "Couldn't reach Booqable",
      kind: 'server',
    })
  })

  it('rewrites a non-AppError failure too', async () => {
    vi.spyOn(http, 'get').mockRejectedValue(new Error('boom'))
    await expect(httpBookingService.list()).rejects.toMatchObject({
      title: "Couldn't reach Booqable",
    })
  })

  it('passes an unauthorized error through unchanged', async () => {
    const error = new AppError({ kind: 'unauthorized', title: 'Signed out', description: 'x' })
    vi.spyOn(http, 'get').mockRejectedValue(error)
    await expect(httpBookingService.list()).rejects.toBe(error)
  })
})
