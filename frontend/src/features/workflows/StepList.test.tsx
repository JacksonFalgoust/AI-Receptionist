import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { emptyStep } from './workflowStepFormSchema'
import type { StepFormValues } from './workflowStepFormSchema'
import { StepList } from './StepList'

function step(overrides: Partial<StepFormValues> = {}): StepFormValues {
  return { ...emptyStep(), id: 'wfs_1', name: 'Check availability', type: 'look_up', ...overrides }
}

describe('StepList', () => {
  it('shows the type and name of every step', () => {
    render(
      <StepList
        steps={[step(), step({ id: 'wfs_2', name: 'End the call', type: 'end' })]}
        selectedId="wfs_1"
        onSelect={vi.fn()}
        onAdd={vi.fn()}
        onMove={vi.fn()}
      />,
    )

    expect(screen.getByText('Look up information')).toBeInTheDocument()
    expect(screen.getByText('Check availability')).toBeInTheDocument()
    expect(screen.getByText('End workflow')).toBeInTheDocument()
    expect(screen.getByText('End the call')).toBeInTheDocument()
  })

  it('shows a step description when it has one', () => {
    render(
      <StepList
        steps={[step({ description: 'Scheduling system, offer alternatives.' })]}
        selectedId="wfs_1"
        onSelect={vi.fn()}
        onAdd={vi.fn()}
        onMove={vi.fn()}
      />,
    )
    expect(screen.getByText('Scheduling system, offer alternatives.')).toBeInTheDocument()
  })

  it('marks the selected step current', () => {
    render(
      <StepList
        steps={[step(), step({ id: 'wfs_2', name: 'End the call' })]}
        selectedId="wfs_2"
        onSelect={vi.fn()}
        onAdd={vi.fn()}
        onMove={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /^(?!Move ).*Check availability/ })).not.toHaveAttribute(
      'aria-current',
    )
    expect(screen.getByRole('button', { name: /^(?!Move ).*End the call/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('selects a step on click', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(
      <StepList
        steps={[step(), step({ id: 'wfs_2', name: 'End the call' })]}
        selectedId="wfs_1"
        onSelect={onSelect}
        onAdd={vi.fn()}
        onMove={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /^(?!Move ).*End the call/ }))
    expect(onSelect).toHaveBeenCalledWith('wfs_2')
  })

  it('adds a step from the header action', async () => {
    const user = userEvent.setup()
    const onAdd = vi.fn()
    render(
      <StepList
        steps={[step()]}
        selectedId="wfs_1"
        onSelect={vi.fn()}
        onAdd={onAdd}
        onMove={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Add step' }))
    expect(onAdd).toHaveBeenCalled()
  })

  it('invites a first step when the workflow has none yet', () => {
    render(
      <StepList steps={[]} selectedId={null} onSelect={vi.fn()} onAdd={vi.fn()} onMove={vi.fn()} />,
    )
    expect(screen.getByText('No steps yet')).toBeInTheDocument()
  })

  it('offers the add action from the empty state too, not just the header', async () => {
    const user = userEvent.setup()
    const onAdd = vi.fn()
    render(
      <StepList steps={[]} selectedId={null} onSelect={vi.fn()} onAdd={onAdd} onMove={vi.fn()} />,
    )

    await user.click(screen.getAllByRole('button', { name: 'Add step' })[1])
    expect(onAdd).toHaveBeenCalled()
  })

  describe('reordering', () => {
    const threeSteps = [
      step({ id: 'wfs_1', name: 'First' }),
      step({ id: 'wfs_2', name: 'Second' }),
      step({ id: 'wfs_3', name: 'Third' }),
    ]

    it('moves a step up', async () => {
      const user = userEvent.setup()
      const onMove = vi.fn()
      render(
        <StepList
          steps={threeSteps}
          selectedId="wfs_2"
          onSelect={vi.fn()}
          onAdd={vi.fn()}
          onMove={onMove}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'Move Second up' }))
      expect(onMove).toHaveBeenCalledWith('wfs_2', 'up')
    })

    it('moves a step down', async () => {
      const user = userEvent.setup()
      const onMove = vi.fn()
      render(
        <StepList
          steps={threeSteps}
          selectedId="wfs_2"
          onSelect={vi.fn()}
          onAdd={vi.fn()}
          onMove={onMove}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'Move Second down' }))
      expect(onMove).toHaveBeenCalledWith('wfs_2', 'down')
    })

    it('has no Move up for the first step, and no Move down for the last', () => {
      render(
        <StepList
          steps={threeSteps}
          selectedId="wfs_1"
          onSelect={vi.fn()}
          onAdd={vi.fn()}
          onMove={vi.fn()}
        />,
      )

      expect(screen.queryByRole('button', { name: 'Move First up' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Move First down' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Move Third up' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Move Third down' })).not.toBeInTheDocument()
    })

    it('does not select the step when a move button is clicked', async () => {
      const user = userEvent.setup()
      const onSelect = vi.fn()
      render(
        <StepList
          steps={threeSteps}
          selectedId="wfs_1"
          onSelect={onSelect}
          onAdd={vi.fn()}
          onMove={vi.fn()}
        />,
      )

      await user.click(screen.getByRole('button', { name: 'Move Second up' }))
      expect(onSelect).not.toHaveBeenCalled()
    })

    it('offers no reordering for a single step', () => {
      render(
        <StepList
          steps={[step({ id: 'wfs_1', name: 'Only step' })]}
          selectedId="wfs_1"
          onSelect={vi.fn()}
          onAdd={vi.fn()}
          onMove={vi.fn()}
        />,
      )

      expect(screen.queryByRole('button', { name: /Move Only step/ })).not.toBeInTheDocument()
    })
  })
})
