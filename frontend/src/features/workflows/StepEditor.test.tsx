import { zodResolver } from '@hookform/resolvers/zod'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm } from 'react-hook-form'

import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog'
import type { SelectOption } from '@/components/ui/Select'

import { StepEditor } from './StepEditor'
import { emptyStep, workflowStepsFormSchema } from './workflowStepFormSchema'
import type { StepFormValues, WorkflowStepsFormValues } from './workflowStepFormSchema'

const integrationOptions: SelectOption[] = [
  { value: 'int_scheduling', label: 'Scheduling' },
  { value: 'int_customer_records', label: 'CRM' },
]

const baseStep: StepFormValues = {
  ...emptyStep(),
  id: 'wfs_1',
  name: 'Check availability',
  description: 'Scheduling system, offer alternatives.',
  type: 'look_up',
  requiredIntegrationId: 'int_scheduling',
  errorBehavior: 'Escalate to a team member',
  escalationBehavior: '',
  configuration: [{ key: 'timeoutSeconds', value: '30' }],
}

function Harness({
  index,
  step = baseStep,
  steps,
  onDelete = vi.fn(),
}: {
  index: number | null
  step?: StepFormValues
  /** Overrides `step` when a test needs more than one step in the same mounted form. */
  steps?: StepFormValues[]
  onDelete?: () => void
}) {
  const form = useForm<WorkflowStepsFormValues>({
    defaultValues: { steps: steps ?? [step] },
    resolver: zodResolver(workflowStepsFormSchema),
  })

  return (
    <ConfirmDialogProvider>
      <FormProvider {...form}>
        <form onSubmit={form.handleSubmit(() => {})}>
          <StepEditor index={index} integrationOptions={integrationOptions} onDelete={onDelete} />
          <button type="submit">Submit</button>
        </form>
      </FormProvider>
    </ConfirmDialogProvider>
  )
}

describe('StepEditor', () => {
  it('invites a selection when no step is selected', () => {
    render(<Harness index={null} />)
    expect(screen.getByText(/select a step/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
  })

  it('renders every PRD §15.4 field for the selected step', () => {
    render(<Harness index={0} />)
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Description')).toBeInTheDocument()
    expect(screen.getByLabelText('Type')).toBeInTheDocument()
    expect(screen.getByLabelText('Required integration')).toBeInTheDocument()
    expect(screen.getByLabelText('Error behavior')).toBeInTheDocument()
    expect(screen.getByLabelText('Escalation behavior')).toBeInTheDocument()
  })

  it('pre-fills from the shared form context', () => {
    render(<Harness index={0} />)
    expect(screen.getByLabelText('Name')).toHaveValue('Check availability')
    expect(screen.getByLabelText('Type')).toHaveValue('look_up')
    expect(screen.getByLabelText('Required integration')).toHaveValue('int_scheduling')
  })

  it('offers every step type as an option', () => {
    render(<Harness index={0} />)
    const select = screen.getByLabelText('Type') as HTMLSelectElement
    expect(within(select).getAllByRole('option')).toHaveLength(9)
  })

  it('offers a way to select no required integration', () => {
    render(<Harness index={0} step={{ ...baseStep, requiredIntegrationId: '' }} />)
    expect(screen.getByLabelText('Required integration')).toHaveValue('')
  })

  it('shows the step\'s configuration rows', () => {
    render(<Harness index={0} />)
    expect(screen.getByDisplayValue('timeoutSeconds')).toBeInTheDocument()
    expect(screen.getByDisplayValue('30')).toBeInTheDocument()
  })

  it('adds a blank configuration row', async () => {
    const user = userEvent.setup()
    render(<Harness index={0} step={{ ...baseStep, configuration: [] }} />)

    await user.click(screen.getByRole('button', { name: 'Add configuration' }))

    expect(screen.getByLabelText('Configuration key')).toBeInTheDocument()
    expect(screen.getByLabelText('Configuration value')).toBeInTheDocument()
  })

  it('removes a configuration row', async () => {
    const user = userEvent.setup()
    render(<Harness index={0} />)

    await user.click(screen.getByRole('button', { name: 'Remove configuration row 1' }))

    expect(screen.queryByDisplayValue('timeoutSeconds')).not.toBeInTheDocument()
  })

  it('gives each configuration row remove button a distinct name', async () => {
    const user = userEvent.setup()
    render(
      <Harness
        index={0}
        step={{
          ...baseStep,
          configuration: [
            { key: 'timeoutSeconds', value: '30' },
            { key: 'retries', value: '2' },
          ],
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Remove configuration row 1' }))

    expect(screen.queryByDisplayValue('timeoutSeconds')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('retries')).toBeInTheDocument()
  })

  it('asks to confirm before deleting a step', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    render(<Harness index={0} onDelete={onDelete} />)

    await user.click(screen.getByRole('button', { name: 'Delete step' }))
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText(/Check availability/)).toBeInTheDocument()

    await user.click(dialog.getByRole('button', { name: 'Delete' }))
    expect(onDelete).toHaveBeenCalled()
  })

  it('does not delete when the confirmation is cancelled', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    render(<Harness index={0} onDelete={onDelete} />)

    await user.click(screen.getByRole('button', { name: 'Delete step' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Cancel' }))

    expect(onDelete).not.toHaveBeenCalled()
  })

  it('shows the newly selected step\'s own configuration, not the previous step\'s stale rows', () => {
    // react-hook-form's useFieldArray does not support a dynamically-changing
    // `name` on one mounted instance — this reproduces switching the selected
    // step within the same mounted form, exactly how WorkflowDetailPage does it.
    const stepA = { ...baseStep, id: 'wfs_a' }
    const stepB = {
      ...emptyStep(),
      id: 'wfs_b',
      name: 'End the call',
      type: 'end' as const,
      configuration: [],
    }
    const { rerender } = render(<Harness steps={[stepA, stepB]} index={0} />)
    expect(screen.getByDisplayValue('timeoutSeconds')).toBeInTheDocument()

    rerender(<Harness steps={[stepA, stepB]} index={1} />)

    expect(screen.queryByDisplayValue('timeoutSeconds')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Configuration key')).not.toBeInTheDocument()
  })

  it('keeps a step\'s own configuration intact after switching away and back', async () => {
    const user = userEvent.setup()
    const stepA = { ...baseStep, id: 'wfs_a' }
    const stepB = {
      ...emptyStep(),
      id: 'wfs_b',
      name: 'End the call',
      type: 'end' as const,
      configuration: [],
    }
    const { rerender } = render(<Harness steps={[stepA, stepB]} index={1} />)

    await user.click(screen.getByRole('button', { name: 'Add configuration' }))
    await user.type(screen.getByLabelText('Configuration key'), 'note')

    rerender(<Harness steps={[stepA, stepB]} index={0} />)
    expect(screen.getByDisplayValue('timeoutSeconds')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('note')).not.toBeInTheDocument()
  })

  it('flags configuration rows that share a key', async () => {
    const user = userEvent.setup()
    render(
      <Harness
        index={0}
        step={{
          ...baseStep,
          configuration: [
            { key: 'timeoutSeconds', value: '30' },
            { key: 'timeoutSeconds', value: '45' },
          ],
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Submit' }))
    expect(await screen.findByText('Configuration keys must be unique.')).toBeInTheDocument()
  })
})
