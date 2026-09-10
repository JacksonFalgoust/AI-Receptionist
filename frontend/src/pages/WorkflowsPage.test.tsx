import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'

import { resetStore, store } from '@/mocks/store'
import { paths } from '@/routes/paths'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { WorkflowsPage } from './WorkflowsPage'

/**
 * `navigate(...)` after creating a workflow has nowhere visible to go unless
 * a real destination route exists — same technique `KnowledgeEditorPage.test.tsx` uses.
 */
function renderPage(route = paths.workflows) {
  return renderWithProviders(
    <Routes>
      <Route path={paths.workflows} element={<WorkflowsPage />} />
      <Route path={paths.workflow()} element={<h1>Workflow detail</h1>} />
    </Routes>,
    { route },
  )
}

describe('WorkflowsPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Workflows' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('renders one row per seeded workflow', async () => {
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(store.workflows.length + 1)
  })

  it('offers a Create workflow CTA in the page header', async () => {
    renderPage()
    await screen.findByRole('table')
    expect(screen.getByRole('button', { name: 'Create workflow' })).toBeInTheDocument()
  })

  it('creates a workflow from the header CTA and moves to its detail page', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table')

    await user.click(screen.getByRole('button', { name: 'Create workflow' }))
    await user.type(await screen.findByLabelText('Name'), 'New client intake follow-up')
    // Two "Create workflow" controls exist while the modal is open: the page
    // header button and the modal's submit button.
    await user.click(screen.getAllByRole('button', { name: 'Create workflow' })[1])

    expect(await screen.findByRole('heading', { name: 'Workflow detail' })).toBeInTheDocument()
    expect(
      store.workflows.some((workflow) => workflow.name === 'New client intake follow-up'),
    ).toBe(true)
  })

  it('invites a first workflow when the list is empty', async () => {
    store.workflows.length = 0
    renderPage()

    expect(await screen.findByText('Create your first workflow')).toBeInTheDocument()
  })

  it('offers the create action from the empty state too, not just the header', async () => {
    store.workflows.length = 0
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Create your first workflow')

    // Two "Create workflow" buttons exist once the list is empty: the page
    // header's and the empty state's own.
    await user.click(screen.getAllByRole('button', { name: 'Create workflow' })[1])
    expect(await screen.findByLabelText('Name')).toBeInTheDocument()
  })
})
