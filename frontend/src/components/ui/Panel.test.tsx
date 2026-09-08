import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Panel, PanelHeader } from './Panel'

describe('Panel', () => {
  it('renders its children inside the panel shell', () => {
    render(<Panel>content</Panel>)
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('merges an extra className onto the shell', () => {
    render(<Panel className="extra">content</Panel>)
    expect(screen.getByText('content')).toHaveClass('extra')
  })
})

describe('PanelHeader', () => {
  it('renders the title as a heading and an optional action', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<PanelHeader title="Recent activity" action={<button onClick={onClick}>View all</button>} />)
    expect(screen.getByRole('heading', { name: 'Recent activity' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'View all' }))
    expect(onClick).toHaveBeenCalledOnce()
  })
})
