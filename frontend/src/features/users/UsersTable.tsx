import { Button } from '@/components/ui/Button'
import { StatusPill } from '@/components/ui/StatusPill'
import { Table } from '@/components/ui/Table'
import type { TableColumn } from '@/components/ui/Table'
import { relativeTime } from '@/lib/formatDate'
import { ROLE_LABELS } from '@/types'
import type { Id, User } from '@/types'

export interface UsersTableProps {
  users: User[]
  /** Marks one row as the signed-in user's own. */
  currentUserId?: Id
  onManage: (user: User) => void
}

/**
 * PRD §19.1's five columns plus a Manage action. Presentational — every
 * mutation on this screen lives in `ManageUserModal`.
 *
 * Columns are defined inline, following `RoutingRulesTable`, rather than
 * extracted the way `knowledgeColumns`/`conversationColumns` are: those screens
 * carry filters and pagination this one does not.
 */
export function UsersTable({ users, currentUserId, onManage }: UsersTableProps) {
  const columns: TableColumn<User>[] = [
    {
      id: 'name',
      header: 'Name',
      render: (user) => (
        <span className="font-medium text-ink">
          {user.name}
          {user.id === currentUserId && ' (you)'}
        </span>
      ),
      sortValue: (user) => user.name,
    },
    {
      id: 'email',
      header: 'Email',
      render: (user) => user.email,
      sortValue: (user) => user.email,
    },
    {
      id: 'role',
      header: 'Role',
      render: (user) => ROLE_LABELS[user.role],
      sortValue: (user) => ROLE_LABELS[user.role],
    },
    {
      id: 'status',
      header: 'Status',
      render: (user) => <StatusPill status={user.status} />,
      sortValue: (user) => user.status,
    },
    {
      id: 'lastLogin',
      header: 'Last login',
      render: (user) =>
        user.lastLoginAt ? (
          relativeTime(user.lastLoginAt)
        ) : (
          <span className="text-ink-secondary">Never signed in</span>
        ),
      // Never-signed-in sorts to the start, where a pending invitation is
      // most likely to be looked for.
      sortValue: (user) => user.lastLoginAt ?? '',
    },
    {
      id: 'actions',
      header: '',
      render: (user) => (
        <Button variant="ghost" size="sm" onClick={() => onManage(user)}>
          Manage
        </Button>
      ),
    },
  ]

  return <Table columns={columns} rows={users} getRowId={(user) => user.id} frame={false} />
}
