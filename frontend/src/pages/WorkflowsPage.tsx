import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Table } from '@/components/ui/Table'
import { CreateWorkflowModal, WORKFLOWS_KEY } from '@/features/workflows/CreateWorkflowModal'
import { WORKFLOW_COLUMNS } from '@/features/workflows/workflowColumns'
import { workflowService } from '@/services/workflowService'

/**
 * US-8.1. PRD §15.1 asks for a plain table with no filters or pagination —
 * unlike Knowledge (C1) or Conversations (B6), neither the PRD nor the
 * prototype's `workflows.html` calls for either here.
 */
export function WorkflowsPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  const query = useQuery({
    queryKey: WORKFLOWS_KEY,
    queryFn: () => workflowService.list(),
  })

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Workflows"
        description="Administer the processes Concierge follows for common customer requests."
        actions={<Button onClick={() => setIsCreateOpen(true)}>Create workflow</Button>}
      />

      <Panel data-testid="workflows-panel">
        <QueryBoundary
          query={query}
          skeleton="table"
          skeletonRows={6}
          isEmpty={(workflows) => workflows.length === 0}
          empty={{
            // PRD §15.1, verbatim.
            title: 'Create your first workflow',
            action: { label: 'Create workflow', onClick: () => setIsCreateOpen(true) },
          }}
        >
          {(workflows) => (
            <Table
              columns={WORKFLOW_COLUMNS}
              rows={workflows}
              getRowId={(workflow) => workflow.id}
              frame={false}
            />
          )}
        </QueryBoundary>
      </Panel>

      <CreateWorkflowModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />
    </div>
  )
}
