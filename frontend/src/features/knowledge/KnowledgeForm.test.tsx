import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { KnowledgeForm } from './KnowledgeForm'
import { emptyKnowledgeFormValues, itemToFormValues } from './knowledgeFormSchema'

function renderForm(props: Partial<React.ComponentProps<typeof KnowledgeForm>> = {}) {
  const onSubmit = vi.fn()
  render(
    <KnowledgeForm
      defaultValues={emptyKnowledgeFormValues()}
      hasExistingSource={false}
      submitLabel="Save"
      onSubmit={onSubmit}
      {...props}
    />,
  )
  return { onSubmit }
}

describe('KnowledgeForm', () => {
  it('renders every field US-5.2 asks for', () => {
    renderForm()
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
    expect(screen.getByLabelText('Type')).toBeInTheDocument()
    expect(screen.getByLabelText('Category')).toBeInTheDocument()
    expect(screen.getByLabelText('Content')).toBeInTheDocument()
    expect(screen.getByLabelText('Tags')).toBeInTheDocument()
    expect(screen.getByLabelText('Active')).toBeInTheDocument()
    expect(screen.getByLabelText('Effective date')).toBeInTheDocument()
    expect(screen.getByLabelText('Expiration date')).toBeInTheDocument()
  })

  it('offers all ten types in business language', async () => {
    renderForm()
    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Type'), 'document')
    expect(screen.getByLabelText('Type')).toHaveValue('document')
  })

  it('shows a website address field only once the type is url', async () => {
    const user = userEvent.setup()
    renderForm()

    expect(screen.queryByLabelText('Website address')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Type'), 'url')
    expect(screen.getByLabelText('Website address')).toBeInTheDocument()
  })

  it('shows a file picker only once the type is document', async () => {
    const user = userEvent.setup()
    renderForm()

    expect(screen.queryByLabelText('File')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Type'), 'document')
    expect(screen.getByLabelText('File')).toBeInTheDocument()
  })

  it('names the file already on record when editing a document', async () => {
    const user = userEvent.setup()
    renderForm({
      defaultValues: itemToFormValues({
        id: 'kn_0022',
        organizationId: 'org_horizon',
        title: 'Client handbook',
        type: 'document',
        status: 'active',
        source: 'client-handbook-2026.pdf',
        tags: [],
        updatedAt: '2026-01-01T00:00:00.000Z',
      }),
      hasExistingSource: true,
      existingSource: 'client-handbook-2026.pdf',
    })
    await user.selectOptions(screen.getByLabelText('Type'), 'document')

    expect(screen.getByText(/client-handbook-2026\.pdf/)).toBeInTheDocument()
  })

  it('explains a system-set status instead of leaving the toggle unexplained', () => {
    // A needs_review item reads Active off, as itemToFormValues maps it —
    // this test supplies that directly rather than round-tripping through it.
    renderForm({
      defaultValues: { ...emptyKnowledgeFormValues('policy'), active: false },
      previousStatus: 'needs_review',
    })

    expect(screen.getByText('Needs review')).toBeInTheDocument()
    expect(screen.getByLabelText('Active')).not.toBeChecked()
  })

  it('shows no status note for a plain new or active item', () => {
    renderForm()
    expect(screen.queryByText('Needs review')).not.toBeInTheDocument()
    expect(screen.queryByText('Processing')).not.toBeInTheDocument()
  })

  it('submits parsed values when the form is valid', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(screen.getByLabelText('Title'), 'Do you offer remote appointments?')
    await user.selectOptions(screen.getByLabelText('Type'), 'faq')
    await user.type(screen.getByLabelText('Content'), 'Yes, by video or phone.')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    // zodResolver validates asynchronously, so the call lands a tick after
    // click; handleSubmit also passes the DOM submit event as a second
    // argument, so the matcher only pins down the first.
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Do you offer remote appointments?', type: 'faq' }),
        expect.anything(),
      ),
    )
  })

  it('shows a validation error and does not submit when the title is blank', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.selectOptions(screen.getByLabelText('Type'), 'faq')
    await user.type(screen.getByLabelText('Content'), 'Some content.')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Enter a title')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('disables the submit button while a save is in flight', () => {
    renderForm({ isSubmitting: true })
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })
})
