import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { InviteUserModal } from './InviteUserModal'

describe('InviteUserModal', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('defaults the role to the least-privileged option', () => {
    renderWithProviders(<InviteUserModal isOpen onClose={vi.fn()} />)
    expect(screen.getByLabelText(/role/i)).toHaveValue('viewer')
  })

  it('rejects an empty form without calling the service', async () => {
    renderWithProviders(<InviteUserModal isOpen onClose={vi.fn()} />)
    const before = store.users.length

    await userEvent.click(screen.getByRole('button', { name: /send invitation/i }))

    expect(await screen.findByText('Enter their full name')).toBeInTheDocument()
    expect(store.users).toHaveLength(before)
  })

  it('rejects a malformed email address', async () => {
    renderWithProviders(<InviteUserModal isOpen onClose={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/full name/i), 'Casey Lin')
    await userEvent.type(screen.getByLabelText(/email/i), 'casey-at-horizon')
    await userEvent.click(screen.getByRole('button', { name: /send invitation/i }))

    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
  })

  it('adds an invited user to the store and closes', async () => {
    const onClose = vi.fn()
    renderWithProviders(<InviteUserModal isOpen onClose={onClose} />)

    await userEvent.type(screen.getByLabelText(/full name/i), 'Casey Lin')
    await userEvent.type(screen.getByLabelText(/email/i), 'casey.lin@horizonpartners.example.com')
    await userEvent.selectOptions(screen.getByLabelText(/role/i), 'analyst')
    await userEvent.click(screen.getByRole('button', { name: /send invitation/i }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())

    const created = store.users.find(
      (user) => user.email === 'casey.lin@horizonpartners.example.com',
    )
    expect(created).toMatchObject({ name: 'Casey Lin', role: 'analyst', status: 'invited' })
    expect(created?.lastLoginAt).toBeUndefined()
    expect(
      screen.getByText('Invitation sent to casey.lin@horizonpartners.example.com.'),
    ).toBeInTheDocument()
  })

  it('puts a duplicate-email failure on the email field, not only in a toast', async () => {
    renderWithProviders(<InviteUserModal isOpen onClose={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/full name/i), 'Duplicate Person')
    await userEvent.type(screen.getByLabelText(/email/i), 'manager@horizonpartners.example.com')
    await userEvent.click(screen.getByRole('button', { name: /send invitation/i }))

    expect(await screen.findByText('This email address already has access.')).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true')
  })
})
