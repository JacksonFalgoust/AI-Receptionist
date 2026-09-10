import { describe, expect, it } from 'vitest'

import { INTEGRATION_ACTION, canDisconnect, integrationAction } from './integrationActions'

describe('integrationActions', () => {
  it('offers nothing to do on a working connection', () => {
    expect(integrationAction('connected')).toBeNull()
  })

  it('maps each broken or unstarted status to its action and service call', () => {
    expect(integrationAction('not_connected')).toMatchObject({ label: 'Connect', kind: 'connect' })
    expect(integrationAction('setup_required')).toMatchObject({
      label: 'Continue setup',
      kind: 'connect',
    })
    expect(integrationAction('connection_error')).toMatchObject({
      label: 'Repair connection',
      kind: 'repair',
    })
    expect(integrationAction('authentication_expired')).toMatchObject({
      label: 'Reconnect',
      kind: 'repair',
    })
  })

  it('gives every action intro copy', () => {
    for (const action of Object.values(INTEGRATION_ACTION)) {
      if (action) expect(action.intro.trim()).not.toBe('')
    }
  })

  it('offers disconnect for everything except a connection that was never made', () => {
    expect(canDisconnect('not_connected')).toBe(false)
    expect(canDisconnect('setup_required')).toBe(true)
    expect(canDisconnect('connection_error')).toBe(true)
    expect(canDisconnect('authentication_expired')).toBe(true)
    expect(canDisconnect('connected')).toBe(true)
  })
})
