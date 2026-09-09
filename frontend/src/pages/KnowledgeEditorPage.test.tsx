import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'

import { resetStore, store } from '@/mocks/store'
import { paths } from '@/routes/paths'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { KnowledgeEditorPage } from './KnowledgeEditorPage'

/**
 * `navigate(...)` has nowhere visible to go unless a real destination route
 * exists, so every test renders the two editor routes alongside a stand-in
 * for the library — the same technique `LoginPage.test.tsx` uses for its own
 * post-submit redirect.
 */
function renderEditor(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path={paths.knowledgeNew} element={<KnowledgeEditorPage />} />
      <Route path={paths.knowledgeItem()} element={<KnowledgeEditorPage />} />
      <Route path={paths.knowledge} element={<h1>Knowledge</h1>} />
    </Routes>,
    { route },
  )
}

describe('KnowledgeEditorPage — add', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', () => {
    renderEditor(paths.knowledgeNew)
    expect(screen.getByRole('heading', { name: 'Add knowledge' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
  })

  it('seeds the type from the add menu', () => {
    renderEditor(`${paths.knowledgeNew}?type=faq`)
    expect(screen.getByLabelText('Type')).toHaveValue('faq')
  })

  it('leaves the type open when nothing was seeded', () => {
    renderEditor(paths.knowledgeNew)
    expect(screen.getByLabelText('Type')).toHaveValue('')
  })

  it('offers no Delete button for an item that does not exist yet', () => {
    renderEditor(paths.knowledgeNew)
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('creates the item, toasts, and returns to the library', async () => {
    const user = userEvent.setup()
    const before = store.knowledge.length
    renderEditor(paths.knowledgeNew)

    await user.type(screen.getByLabelText('Title'), 'Do you offer remote appointments?')
    await user.selectOptions(screen.getByLabelText('Type'), 'faq')
    await user.type(screen.getByLabelText('Content'), 'Yes, by video or phone.')
    await user.click(screen.getByRole('button', { name: 'Add knowledge' }))

    expect(await screen.findByRole('heading', { name: 'Knowledge' })).toBeInTheDocument()
    expect(store.knowledge).toHaveLength(before + 1)
    expect(
      store.knowledge.find((item) => item.title === 'Do you offer remote appointments?'),
    ).toBeTruthy()
  })
})

describe('KnowledgeEditorPage — edit', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('loads the item behind a loading state, then shows its values', async () => {
    renderEditor(paths.knowledgeItem('kn_0006'))

    expect(screen.getByRole('status')).toBeInTheDocument()

    expect(await screen.findByDisplayValue('Cancellation policy')).toBeInTheDocument()
    expect(screen.getByLabelText('Type')).toHaveValue('policy')
  })

  it('says plainly when the item no longer exists, with a way back', async () => {
    renderEditor(paths.knowledgeItem('kn_9999'))

    expect(await screen.findByRole('alert')).toHaveTextContent(/no longer exists/i)
    await userEvent.setup().click(screen.getByRole('link', { name: 'Back to Knowledge' }))
    expect(await screen.findByRole('heading', { name: 'Knowledge' })).toBeInTheDocument()
  })

  it('explains a status the system set rather than showing a bare toggle', async () => {
    // kn_0008 seeds as needs_review in mocks/knowledge.ts.
    renderEditor(paths.knowledgeItem('kn_0008'))

    await screen.findByDisplayValue('Privacy commitment')
    expect(screen.getByText('Needs review')).toBeInTheDocument()
    expect(screen.getByLabelText('Active')).not.toBeChecked()
  })

  it('saves a change, toasts, and returns to the library', async () => {
    const user = userEvent.setup()
    renderEditor(paths.knowledgeItem('kn_0006'))

    const title = await screen.findByDisplayValue('Cancellation policy')
    await user.clear(title)
    await user.type(title, 'Cancellation policy (updated)')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('heading', { name: 'Knowledge' })).toBeInTheDocument()
    const saved = store.knowledge.find((item) => item.id === 'kn_0006')
    expect(saved?.title).toBe('Cancellation policy (updated)')
    // A save that never touched the source must not blank it — the library's
    // Source column has nothing else to show.
    expect(saved?.source).toBe('Manual entry')
  })

  it('deletes only after confirming', async () => {
    const user = userEvent.setup()
    renderEditor(paths.knowledgeItem('kn_0006'))
    await screen.findByDisplayValue('Cancellation policy')

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Cancel' }))

    expect(store.knowledge.some((item) => item.id === 'kn_0006')).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    const confirmDialog = within(await screen.findByRole('dialog'))
    await user.click(confirmDialog.getByRole('button', { name: 'Delete' }))

    expect(await screen.findByRole('heading', { name: 'Knowledge' })).toBeInTheDocument()
    expect(store.knowledge.some((item) => item.id === 'kn_0006')).toBe(false)
  })
})
