import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { UsersPage } from './UsersPage'

describe('UsersPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession('owner@horizonpartners.example.com')
  })

  it('lists every seeded user once loaded', async () => {
    renderWithProviders(<UsersPage />)

    expect(await screen.findByText(/Jordan Lee/)).toBeInTheDocument()
    expect(screen.getByText('Robin Alvarez')).toBeInTheDocument()
    expect(screen.getByText('Morgan Vance')).toBeInTheDocument()
  })

  it('marks the signed-in user row', async () => {
    renderWithProviders(<UsersPage />)
    // A plain text regex can't match this: "(you)" is rendered in a nested
    // <span>, so it isn't part of any single node's direct text (see
    // UsersTable.test.tsx's identical `element?.textContent` matcher for the
    // same reason). `screen.findByText(/Jordan Lee \(you\)/)` never resolves.
    expect(
      await screen.findByText(
        (_, element) =>
          element?.classList.contains('font-medium') === true &&
          element?.textContent === 'Jordan Lee (you)',
      ),
    ).toBeInTheDocument()
  })

  it('invites a user end to end', async () => {
    renderWithProviders(<UsersPage />)
    await screen.findByText(/Jordan Lee/)

    await userEvent.click(screen.getByRole('button', { name: /invite user/i }))
    // Scoped to the dialog: UsersTable's "Sort by Email" column header button
    // carries `aria-label="Sort by Email"`, which `getByLabelText(/email/i)`
    // also matches unscoped, making it ambiguous against the unfiltered page.
    const dialog = within(await screen.findByRole('dialog', { name: /invite user/i }))
    await userEvent.type(dialog.getByLabelText(/full name/i), 'Casey Lin')
    await userEvent.type(dialog.getByLabelText(/email/i), 'casey.lin@horizonpartners.example.com')
    await userEvent.click(dialog.getByRole('button', { name: /send invitation/i }))

    await waitFor(() =>
      expect(
        store.users.some((user) => user.email === 'casey.lin@horizonpartners.example.com'),
      ).toBe(true),
    )
    expect(await screen.findByText('Casey Lin')).toBeInTheDocument()
  })

  it('opens the manage modal for a chosen row', async () => {
    renderWithProviders(<UsersPage />)
    await screen.findByText(/Jordan Lee/)

    const rows = screen.getAllByRole('button', { name: /^manage$/i })
    await userEvent.click(rows[0])

    expect(await screen.findByRole('dialog', { name: /manage jordan lee/i })).toBeInTheDocument()
  })
})
