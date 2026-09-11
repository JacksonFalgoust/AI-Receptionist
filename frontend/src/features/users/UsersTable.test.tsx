import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { User } from '@/types'

import { UsersTable } from './UsersTable'

const USERS: User[] = [
  {
    id: 'user_owner',
    organizationId: 'org_horizon',
    name: 'Jordan Lee',
    email: 'owner@horizonpartners.example.com',
    role: 'owner',
    status: 'active',
    lastLoginAt: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'user_invited',
    organizationId: 'org_horizon',
    name: 'Robin Alvarez',
    email: 'robin.alvarez@horizonpartners.example.com',
    role: 'manager',
    status: 'invited',
  },
]

describe('UsersTable', () => {
  it('renders PRD 19.1 five columns', () => {
    render(<UsersTable users={USERS} currentUserId="user_owner" onManage={vi.fn()} />)

    for (const header of ['Name', 'Email', 'Role', 'Status', 'Last login']) {
      expect(screen.getByRole('columnheader', { name: new RegExp(header, 'i') })).toBeInTheDocument()
    }
  })

  it('shows a role label rather than the stored value', () => {
    render(<UsersTable users={USERS} currentUserId="user_owner" onManage={vi.fn()} />)
    expect(screen.getByText('Owner')).toBeInTheDocument()
    expect(screen.getByText('Manager')).toBeInTheDocument()
  })

  it('marks a pending invitation with a pill and never-signed-in copy', () => {
    render(<UsersTable users={USERS} currentUserId="user_owner" onManage={vi.fn()} />)
    expect(screen.getByText('Invited')).toBeInTheDocument()
    // Never having signed in is an answer, not missing data, so it reads as a
    // sentence rather than the em dash a genuinely unknown value would get.
    expect(screen.getByText('Never signed in')).toBeInTheDocument()
    expect(screen.getByText('1 hour ago')).toBeInTheDocument()
  })

  it('marks the signed-in user own row', () => {
    render(<UsersTable users={USERS} currentUserId="user_owner" onManage={vi.fn()} />)
    expect(
      screen.getByText((_, element) => {
        return (
          element?.classList.contains('font-medium') === true &&
          element?.textContent === 'Jordan Lee (you)'
        )
      }),
    ).toBeInTheDocument()
    expect(
      screen.queryByText((_, element) => {
        return (
          element?.classList.contains('font-medium') === true &&
          element?.textContent === 'Robin Alvarez (you)'
        )
      }),
    ).not.toBeInTheDocument()
  })

  it('hands the whole user back when Manage is clicked', async () => {
    const onManage = vi.fn()
    render(<UsersTable users={USERS} currentUserId="user_owner" onManage={onManage} />)

    await userEvent.click(screen.getAllByRole('button', { name: /manage/i })[1])
    expect(onManage).toHaveBeenCalledWith(USERS[1])
  })
})
