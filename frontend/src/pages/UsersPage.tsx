import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/useAuth'
import { InviteUserModal } from '@/features/users/InviteUserModal'
import { ManageUserModal } from '@/features/users/ManageUserModal'
import { UsersTable } from '@/features/users/UsersTable'
import { USERS_KEY } from '@/features/users/usersQuery'
import { userService } from '@/services/userService'
import type { User } from '@/types'

/** US-11.1 / PRD §19. Owner and Administrator only (`manage:users`). */
export function UsersPage() {
  const { user: signedIn } = useAuth()

  const usersQuery = useQuery({
    queryKey: USERS_KEY,
    queryFn: () => userService.list(),
  })

  const [isInviting, setInviting] = useState(false)
  const [managed, setManaged] = useState<User | null>(null)

  const users = usersQuery.data ?? []

  // The managed user is re-read from the freshly-loaded list each render, so a
  // modal that is open when a mutation lands shows the updated person rather
  // than the snapshot it was opened with.
  const managedUser = managed ? (users.find((user) => user.id === managed.id) ?? null) : null

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Users & Roles"
        description="Manage who can operate, configure, and oversee Concierge."
        actions={<Button onClick={() => setInviting(true)}>Invite user</Button>}
      />

      <Panel>
        <QueryBoundary
          query={usersQuery}
          skeletonRows={6}
          isEmpty={(loaded) => loaded.length === 0}
          empty={{
            title: 'Invite your first teammate',
            description:
              'People you invite can operate, configure, or simply review Concierge, depending on the role you give them.',
            action: { label: 'Invite user', onClick: () => setInviting(true) },
          }}
        >
          {(loaded) => (
            <UsersTable
              users={loaded}
              currentUserId={signedIn?.id}
              onManage={(user) => setManaged(user)}
            />
          )}
        </QueryBoundary>
      </Panel>

      <InviteUserModal isOpen={isInviting} onClose={() => setInviting(false)} />

      <ManageUserModal
        isOpen={managedUser !== null}
        onClose={() => setManaged(null)}
        user={managedUser}
        users={users}
      />
    </div>
  )
}
