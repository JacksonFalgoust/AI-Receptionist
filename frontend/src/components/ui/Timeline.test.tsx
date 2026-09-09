import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'

import { Timeline } from './Timeline'

describe('Timeline', () => {
  it('renders one list item per entry with its time, title, and meta', () => {
    render(
      <Timeline
        items={[
          { id: '1', time: '10:02 AM', title: 'Looked up reservation', meta: 'Booqable' },
          { id: '2', time: '10:03 AM', title: 'Sent confirmation', tone: 'error' },
        ]}
      />,
    )
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(screen.getByText('Looked up reservation')).toBeInTheDocument()
    expect(screen.getByText('Booqable')).toBeInTheDocument()
    expect(screen.getByText('Sent confirmation')).toBeInTheDocument()

    expect(items[0].querySelector('span')).toHaveClass('bg-brand')
    expect(items[1].querySelector('span')).toHaveClass('bg-danger')

    expect(items[0].querySelectorAll('p')).toHaveLength(3) // time, title, meta
    expect(items[1].querySelectorAll('p')).toHaveLength(2) // time, title only
  })

  it('tucks optional details behind a disclosure, collapsed by default', () => {
    render(
      <Timeline
        items={[
          {
            id: '1',
            time: '10:02 AM',
            title: 'Create appointment',
            meta: 'Scheduling',
            details: <dl><dt>attempts</dt><dd>2</dd></dl>,
          },
        ]}
      />,
    )

    const disclosure = screen.getByRole('group')
    expect(disclosure).not.toHaveAttribute('open')
    expect(within(disclosure).getByText('System details')).toBeInTheDocument()
    expect(within(disclosure).getByText('attempts')).toBeInTheDocument()
  })

  it('renders no disclosure for an entry without details', () => {
    render(<Timeline items={[{ id: '1', time: '10:02 AM', title: 'Call ended' }]} />)

    expect(screen.queryByRole('group')).not.toBeInTheDocument()
  })
})
