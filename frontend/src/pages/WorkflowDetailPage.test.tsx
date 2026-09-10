import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'

import { resetStore, store } from '@/mocks/store'
import { paths } from '@/routes/paths'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { WorkflowDetailPage } from './WorkflowDetailPage'

function renderPage(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path={paths.workflow()} element={<WorkflowDetailPage />} />
      <Route path={paths.workflows} element={<h1>Workflows</h1>} />
    </Routes>,
    { route },
  )
}

describe('WorkflowDetailPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderPage(paths.workflow('wf_booking'))
    expect(await screen.findByRole('heading', { name: 'Book an appointment' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
  })

  it('shows a breadcrumb back to the list', async () => {
    renderPage(paths.workflow('wf_booking'))
    await screen.findByRole('heading', { name: 'Book an appointment' })
    expect(screen.getByRole('link', { name: 'Workflows' })).toHaveAttribute(
      'href',
      '/concierge/workflows',
    )
  })

  it('lists every step of the workflow', async () => {
    renderPage(paths.workflow('wf_booking'))
    await screen.findByRole('heading', { name: 'Book an appointment' })

    const stepList = within(screen.getByTestId('step-list-panel'))
    for (const step of store.workflows.find((w) => w.id === 'wf_booking')!.steps) {
      expect(stepList.getByText(step.name)).toBeInTheDocument()
    }
  })

  it('loads the first step into the editor by default', async () => {
    renderPage(paths.workflow('wf_booking'))
    expect(await screen.findByLabelText('Name')).toHaveValue('Ask what the client needs')
  })

  it('loads a different step into the editor on selection', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await user.click(screen.getByRole('button', { name: /^(?!Move ).*Confirm the chosen time/ }))

    expect(screen.getByLabelText('Name')).toHaveValue('Confirm the chosen time')
  })

  it('offers the connected integrations as required-integration options', async () => {
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: /^(?!Move ).*Check the client record/ }))
    expect(screen.getByLabelText('Required integration')).toHaveValue('int_customer_records')
    expect(screen.getByText('Customer Records')).toBeInTheDocument()
  })

  it('saves an edit as a draft without publishing', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await user.clear(screen.getByLabelText('Name'))
    await user.type(screen.getByLabelText('Name'), 'Ask what the client needs today')
    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    expect(await screen.findByText('Draft saved.')).toBeInTheDocument()
    const workflow = store.workflows.find((w) => w.id === 'wf_booking')!
    expect(workflow.steps[0].name).toBe('Ask what the client needs today')
    expect(workflow.status).toBe('active')
    expect(workflow.version).toBe(7)
  })

  it('moves a step and saves the new order', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    const before = store.workflows.find((w) => w.id === 'wf_booking')!.steps.map((s) => s.name)
    await user.click(screen.getByRole('button', { name: `Move ${before[1]} up` }))
    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    expect(await screen.findByText('Draft saved.')).toBeInTheDocument()
    const workflow = store.workflows.find((w) => w.id === 'wf_booking')!
    expect(workflow.steps[0].name).toBe(before[1])
    expect(workflow.steps[1].name).toBe(before[0])
  })

  it('keeps the step selected in the editor after moving it', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await user.click(screen.getByRole('button', { name: /^(?!Move ).*Confirm the chosen time/ }))
    await user.click(screen.getByRole('button', { name: 'Move Confirm the chosen time up' }))

    expect(screen.getByLabelText('Name')).toHaveValue('Confirm the chosen time')
  })

  it('shows the moved step\'s own configuration after reordering, not the row count of whichever step now sits at its old position', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    const firstStepName = await screen.findByLabelText('Name')
    expect(firstStepName).toHaveValue('Ask what the client needs')

    await user.click(screen.getByRole('button', { name: 'Add configuration' }))
    await user.type(screen.getByLabelText('Configuration key'), 'note')

    await user.click(screen.getByRole('button', { name: 'Move Ask what the client needs down' }))

    expect(screen.getByLabelText('Name')).toHaveValue('Ask what the client needs')
    expect(screen.getByDisplayValue('note')).toBeInTheDocument()
  })

  it('adds a step and saves it', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await user.click(screen.getByRole('button', { name: 'Add step' }))
    await user.type(screen.getByLabelText('Name'), 'Send a reminder text')
    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    expect(await screen.findByText('Draft saved.')).toBeInTheDocument()
    const workflow = store.workflows.find((w) => w.id === 'wf_booking')!
    expect(workflow.steps).toHaveLength(8)
    expect(workflow.steps.at(-1)).toMatchObject({ name: 'Send a reminder text' })
  })

  it('deletes a step, once confirmed, and saves the removal', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await user.click(screen.getByRole('button', { name: 'Delete step' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Delete' }))
    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    expect(await screen.findByText('Draft saved.')).toBeInTheDocument()
    const workflow = store.workflows.find((w) => w.id === 'wf_booking')!
    expect(workflow.steps).toHaveLength(6)
    expect(workflow.steps.some((step) => step.name === 'Ask what the client needs')).toBe(false)
  })

  it('publishes once confirmed, bumping the version', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await user.click(screen.getByRole('button', { name: 'Publish' }))
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText(/immediately use/)).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Publish' }))

    expect(await screen.findByText('Workflow published.')).toBeInTheDocument()
    const workflow = store.workflows.find((w) => w.id === 'wf_booking')!
    expect(workflow.version).toBe(8)
    expect(workflow.status).toBe('active')
  })

  it('does not publish when the confirmation is cancelled', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_booking'))
    await screen.findByLabelText('Name')

    await user.click(screen.getByRole('button', { name: 'Publish' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Cancel' }))

    expect(store.workflows.find((w) => w.id === 'wf_booking')!.version).toBe(7)
  })

  it('blocks publishing a workflow with no steps, without asking to confirm', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_onboarding'))
    await screen.findByLabelText('Name')

    // Delete every seeded step first.
    for (let i = 0; i < 3; i += 1) {
      await user.click(screen.getByRole('button', { name: 'Delete step' }))
      const dialog = within(await screen.findByRole('dialog'))
      await user.click(dialog.getByRole('button', { name: 'Delete' }))
    }
    await screen.findByText('No steps yet')

    await user.click(screen.getByRole('button', { name: 'Publish' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(await screen.findByText(/at least one step/i)).toBeInTheDocument()
  })

  it('says plainly when the workflow does not exist, with a way back', async () => {
    const user = userEvent.setup()
    renderPage(paths.workflow('wf_9999'))

    expect(await screen.findByRole('alert')).toHaveTextContent(/no longer exists/i)
    await user.click(screen.getByRole('link', { name: 'Back to workflows' }))
    expect(await screen.findByRole('heading', { name: 'Workflows' })).toBeInTheDocument()
  })
})
