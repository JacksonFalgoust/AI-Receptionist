import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'

import { resetStore, store } from '@/mocks/store'
import { paths } from '@/routes/paths'
import { workflowService } from '@/services/workflowService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'
import type { Workflow } from '@/types'

import { CreateWorkflowModal } from './CreateWorkflowModal'

function renderModal(onClose = vi.fn()) {
  return {
    onClose,
    ...renderWithProviders(
      <Routes>
        <Route
          path={paths.workflows}
          element={<CreateWorkflowModal isOpen onClose={onClose} />}
        />
        <Route path={paths.workflow()} element={<h1>Workflow detail</h1>} />
      </Routes>,
      { route: paths.workflows },
    ),
  }
}

describe('CreateWorkflowModal', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('renders nothing when closed', () => {
    renderWithProviders(<CreateWorkflowModal isOpen={false} onClose={vi.fn()} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('asks for a name before creating', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('button', { name: 'Create workflow' }))

    expect(await screen.findByText('Name is required.')).toBeInTheDocument()
  })

  it('creates the workflow and moves to its detail page', async () => {
    const user = userEvent.setup()
    const before = store.workflows.length
    renderModal()

    await user.type(screen.getByLabelText('Name'), 'Cancel a booking')
    await user.type(screen.getByLabelText('Description (optional)'), 'Cancels an existing reservation.')
    await user.click(screen.getByRole('button', { name: 'Create workflow' }))

    expect(await screen.findByRole('heading', { name: 'Workflow detail' })).toBeInTheDocument()
    expect(store.workflows).toHaveLength(before + 1)
    const created = store.workflows.find((workflow) => workflow.name === 'Cancel a booking')
    expect(created).toMatchObject({
      description: 'Cancels an existing reservation.',
      status: 'draft',
      version: 1,
    })
  })

  it('closes without creating anything when cancelled', async () => {
    const user = userEvent.setup()
    const before = store.workflows.length
    const { onClose } = renderModal()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
    expect(store.workflows).toHaveLength(before)
  })

  it('clears the name error as soon as a name is typed', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('button', { name: 'Create workflow' }))
    expect(await screen.findByText('Name is required.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Name'), 'C')
    expect(screen.queryByText('Name is required.')).not.toBeInTheDocument()
  })

  it('will not let Cancel abandon an in-flight create', async () => {
    const user = userEvent.setup()
    // The mock service's own latency is 0 under test, so a real in-flight
    // window is forced here by holding the create promise open by hand.
    let resolveCreate!: (workflow: Workflow) => void
    const createSpy = vi
      .spyOn(workflowService, 'create')
      .mockReturnValue(new Promise((resolve) => (resolveCreate = resolve)))
    const { onClose } = renderModal()

    await user.type(screen.getByLabelText('Name'), 'Cancel a booking')
    await user.click(screen.getByRole('button', { name: 'Create workflow' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    resolveCreate({
      id: 'wf_test',
      organizationId: 'org_horizon',
      name: 'Cancel a booking',
      status: 'draft',
      version: 1,
      steps: [],
      executionCount: 0,
      lastUpdatedAt: new Date().toISOString(),
    })

    expect(await screen.findByRole('heading', { name: 'Workflow detail' })).toBeInTheDocument()
    createSpy.mockRestore()
  })
})
