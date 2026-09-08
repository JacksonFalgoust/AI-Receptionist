import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { ChatBubble } from './ChatBubble'

describe('ChatBubble', () => {
  it('labels the speaker and renders the message', () => {
    render(<ChatBubble speaker="customer" message="Can I move my reservation?" />)
    expect(screen.getByText('Customer')).toBeInTheDocument()
    expect(screen.getByText('Can I move my reservation?')).toBeInTheDocument()
  })

  it('renders a distinct label per speaker', () => {
    render(<ChatBubble speaker="concierge" message="Sure, what date works?" />)
    expect(screen.getByText('Concierge')).toBeInTheDocument()
  })

  it('renders the timestamp when given', () => {
    render(<ChatBubble speaker="employee" message="Approved." time="9:45 AM" />)
    expect(screen.getByText('9:45 AM')).toBeInTheDocument()
  })
})
