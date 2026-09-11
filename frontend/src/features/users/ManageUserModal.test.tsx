import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { resetStore, store } from '@/mocks/store'
import type { User } from '@/types'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ManageUserModal } from './ManageUserModal'

function find(id: string): User {
  const user = store.users.find((candidate) => candidate.id === id)
  if (!user) throw new Error(`No seeded user ${id}`)
  return user
}

function open(userId: string, onClose = vi.fn()) {
  return {
    onClose,
    ...renderWithProviders(
      <ManageUserModal isOpen onClose={onClose} user={find(userId)} users={store.users} />,
    ),
  }
}

describe('ManageUserModal', () => {
  beforeEach(() => {
    resetStore()
    seedSession('administrator@horizonpartners.example.com')
  })

  it('saves a new role', async () => {
    const { onClose } = open('user_viewer')

    await userEvent.selectOptions(screen.getByLabelText(/role/i), 'analyst')
    await userEvent.click(screen.getByRole('button', { name: /save role/i }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(find('user_viewer').role).toBe('analyst')
  })

  it('offers Resend invitation only for a pending invitation', async () => {
    open('user_invited_agent')
    expect(screen.getByRole('button', { name: /resend invitation/i })).toBeInTheDocument()
  })

  it('hides Resend invitation for someone who has accepted', () => {
    open('user_viewer')
    expect(screen.queryByRole('button', { name: /resend invitation/i })).not.toBeInTheDocument()
  })

  it('resends an invitation and reports it', async () => {
    open('user_invited_agent')

    await userEvent.click(screen.getByRole('button', { name: /resend invitation/i }))

    expect(
      await screen.findByText('Invitation resent to jamie.okafor@horizonpartners.example.com.'),
    ).toBeInTheDocument()
  })

  it('disables access behind a confirmation', async () => {
    open('user_agent')

    await userEvent.click(screen.getByRole('button', { name: 'Disable access' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Disable' }))

    await waitFor(() => expect(find('user_agent').status).toBe('disabled'))
  })

  it('restores access without a confirmation', async () => {
    open('user_disabled')

    await userEvent.click(screen.getByRole('button', { name: /restore access/i }))

    await waitFor(() => expect(find('user_disabled').status).toBe('active'))
  })

  it('removes a user behind a confirmation naming the consequence', async () => {
    open('user_viewer')

    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(
      await screen.findByText(/Chris Nguyen will lose access to Horizon Partners immediately/),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove user' }))

    await waitFor(() =>
      expect(store.users.some((user) => user.id === 'user_viewer')).toBe(false),
    )
  })

  it('leaves the user in place when the confirmation is cancelled', async () => {
    open('user_viewer')

    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await userEvent.click(await screen.findByRole('button', { name: /cancel/i }))

    expect(store.users.some((user) => user.id === 'user_viewer')).toBe(true)
  })

  it('blocks every guarded action on your own row, with the reason on screen', async () => {
    seedSession('owner@horizonpartners.example.com')
    open('user_owner')

    expect(screen.getByLabelText(/role/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Disable access' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled()
    expect(screen.getByText("You can't change your own role.")).toBeInTheDocument()
    expect(screen.getByText("You can't remove your own access.")).toBeInTheDocument()
  })

  it('blocks removing the only active owner, naming the organization', () => {
    open('user_owner')

    expect(screen.getByRole('button', { name: 'Remove' })).toBeDisabled()
    expect(
      screen.getAllByText('Horizon Partners needs at least one Owner.').length,
    ).toBeGreaterThan(0)
  })

  it('renders nothing when no user is selected', () => {
    renderWithProviders(<ManageUserModal isOpen onClose={vi.fn()} user={null} users={[]} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
