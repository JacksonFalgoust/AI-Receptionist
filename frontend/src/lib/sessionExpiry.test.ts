import { describe, expect, it, vi } from 'vitest'

import { notifySessionExpired, onSessionExpired } from './sessionExpiry'

describe('sessionExpiry', () => {
  it('calls a subscribed handler on notify', () => {
    const handler = vi.fn()
    const unsubscribe = onSessionExpired(handler)

    notifySessionExpired()

    expect(handler).toHaveBeenCalledOnce()
    unsubscribe()
  })

  it('stops calling a handler once unsubscribed', () => {
    const handler = vi.fn()
    const unsubscribe = onSessionExpired(handler)

    unsubscribe()
    notifySessionExpired()

    expect(handler).not.toHaveBeenCalled()
  })

  it('calls every subscribed handler', () => {
    const first = vi.fn()
    const second = vi.fn()
    const unsubFirst = onSessionExpired(first)
    const unsubSecond = onSessionExpired(second)

    notifySessionExpired()

    expect(first).toHaveBeenCalledOnce()
    expect(second).toHaveBeenCalledOnce()
    unsubFirst()
    unsubSecond()
  })

  it('tolerates a handler unsubscribing itself during notify', () => {
    const survivor = vi.fn()
    let unsubSelf: () => void = () => {}
    unsubSelf = onSessionExpired(() => unsubSelf())
    const unsubSurvivor = onSessionExpired(survivor)

    expect(() => notifySessionExpired()).not.toThrow()
    expect(survivor).toHaveBeenCalledOnce()
    unsubSurvivor()
  })
})
