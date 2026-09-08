import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Tabs } from './Tabs'

const items = [
  { value: 'summary', label: 'Summary' },
  { value: 'transcript', label: 'Transcript' },
  { value: 'actions', label: 'Actions' },
]

function Harness() {
  const [value, setValue] = useState('summary')
  return (
    <Tabs items={items} value={value} onChange={setValue}>
      <p>Panel: {value}</p>
    </Tabs>
  )
}

describe('Tabs', () => {
  it('marks only the active tab as selected and renders its panel', () => {
    render(<Harness />)
    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Transcript' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByText('Panel: summary')).toBeInTheDocument()
  })

  it('switches tabs on click', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('tab', { name: 'Transcript' }))
    expect(screen.getByRole('tab', { name: 'Transcript' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('Panel: transcript')).toBeInTheDocument()
  })

  it('moves focus and selection with ArrowRight, wrapping past the last tab back to the first', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('tab', { name: 'Summary' }).focus()

    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Transcript' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Transcript' })).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveFocus()

    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveFocus()
  })

  it('moves focus and selection with ArrowLeft, wrapping past the first tab back to the last', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('tab', { name: 'Summary' }).focus()

    await user.keyboard('{ArrowLeft}')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
  })

  it('jumps to the first tab on Home and the last tab on End', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('tab', { name: 'Transcript' }).focus()

    await user.keyboard('{End}')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')

    await user.keyboard('{Home}')
    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveAttribute('aria-selected', 'true')
  })

  it('scopes tab/panel DOM ids per instance so two Tabs on one page never collide', () => {
    function TwoInstances() {
      const [a, setA] = useState('summary')
      const [b, setB] = useState('summary')
      return (
        <>
          <Tabs items={items} value={a} onChange={setA}>
            panel-a
          </Tabs>
          <Tabs items={items} value={b} onChange={setB}>
            panel-b
          </Tabs>
        </>
      )
    }
    render(<TwoInstances />)
    const summaryTabs = screen.getAllByRole('tab', { name: 'Summary' })
    expect(summaryTabs).toHaveLength(2)
    expect(summaryTabs[0].id).not.toBe(summaryTabs[1].id)
  })
})
