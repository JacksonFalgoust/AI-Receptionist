import { describe, expect, it } from 'vitest'

import { testConciergeService } from './testConciergeService'

describe('testConciergeService', () => {
  it('answers an hours question using the seeded FAQ, with no workflow or integration', async () => {
    const reply = await testConciergeService.simulate('What are your opening hours?')
    expect(reply.knowledgeUsed).toEqual(['What are your opening hours?'])
    expect(reply.workflowUsed).toBeUndefined()
    expect(reply.integrationsUsed).toBeUndefined()
    expect(reply.actionsExecuted).toBeUndefined()
  })

  it('matches case-insensitively', async () => {
    const reply = await testConciergeService.simulate('WHEN ARE YOU OPEN')
    expect(reply.knowledgeUsed).toEqual(['What are your opening hours?'])
  })

  it('cites the booking workflow and scheduling integration for a booking request', async () => {
    const reply = await testConciergeService.simulate('I need to book an appointment')
    expect(reply.workflowUsed).toBe('Book an appointment')
    expect(reply.integrationsUsed).toEqual(['Scheduling'])
    expect(reply.actionsExecuted).toEqual(['Checked availability', 'Created a hold'])
  })

  it('cites the reschedule workflow for a cancellation request', async () => {
    const reply = await testConciergeService.simulate('I need to cancel my appointment')
    expect(reply.workflowUsed).toBe('Reschedule an appointment')
    expect(reply.knowledgeUsed).toEqual(['How do I reschedule an appointment?'])
  })

  it('cites the payment workflow and integration for a billing question', async () => {
    const reply = await testConciergeService.simulate('How do I pay my invoice?')
    expect(reply.workflowUsed).toBe('Send a payment link')
    expect(reply.integrationsUsed).toEqual(['Payments'])
    expect(reply.actionsExecuted).toEqual(['Sent a payment link'])
  })

  it('cites the complaint workflow and customer records integration', async () => {
    const reply = await testConciergeService.simulate("I'm really unhappy with my service")
    expect(reply.workflowUsed).toBe('Handle a complaint')
    expect(reply.integrationsUsed).toEqual(['Customer Records'])
  })

  it('falls back to a generic reply with no metadata for an unrecognised message', async () => {
    const reply = await testConciergeService.simulate('Hello there!')
    expect(reply.reply).toMatch(/scheduling, billing/i)
    expect(reply.workflowUsed).toBeUndefined()
    expect(reply.knowledgeUsed).toBeUndefined()
    expect(reply.integrationsUsed).toBeUndefined()
    expect(reply.actionsExecuted).toBeUndefined()
  })

  it('assigns a unique id and timestamp per call, and never echoes the input message back', async () => {
    const first = await testConciergeService.simulate('hello')
    const second = await testConciergeService.simulate('hello')
    expect(first.id).not.toBe(second.id)
    expect(first.createdAt).toEqual(expect.any(String))
    expect(first).not.toHaveProperty('customerMessage')
  })
})
