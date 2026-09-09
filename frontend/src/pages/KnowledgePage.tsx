import { useQuery } from '@tanstack/react-query'

import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { Panel } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Table } from '@/components/ui/Table'
import { AddKnowledgeMenu, addKnowledgeHref } from '@/features/knowledge/AddKnowledgeMenu'
import { KNOWLEDGE_COLUMNS } from '@/features/knowledge/knowledgeColumns'
import { KnowledgeFilterBar } from '@/features/knowledge/KnowledgeFilterBar'
import { useKnowledgeFilters } from '@/features/knowledge/useKnowledgeFilters'
import { knowledgeService } from '@/services/knowledgeService'

/**
 * US-5.1: everything Concierge knows, in one table. Search, type and status
 * live in the URL, so "everything that needs review" is a link somebody can
 * send to a colleague.
 */
export function KnowledgePage() {
  const { state, params, activeCount, setFilter, setPage, clear } = useKnowledgeFilters()

  const query = useQuery({
    // [namespace, entity, variable], as everywhere else — keeps a future
    // ['knowledge', id] detail query from colliding with this one.
    queryKey: ['knowledge', 'list', params],
    queryFn: () => knowledgeService.list(params),
  })

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Knowledge"
        description="Manage the information Concierge uses when responding to customers."
        actions={<AddKnowledgeMenu />}
      />
      <div className="space-y-3">
        <KnowledgeFilterBar
          state={state}
          activeCount={activeCount}
          onChange={setFilter}
          onClear={clear}
        />

        {/* Loading, empty, error and success all render inside this one Panel
            so the page doesn't reflow the moment data lands. */}
        <Panel data-testid="knowledge-panel">
          <QueryBoundary
            query={query}
            skeleton="table"
            skeletonRows={8}
            // Not `items.length === 0`: an out-of-range page — a bookmark kept
            // after the library shrank — has no items but a non-zero total,
            // and must render the table shell and a working Pagination rather
            // than claim nothing exists.
            isEmpty={(page) => page.total === 0}
            // Two different problems needing two different answers: nothing
            // has been added yet, versus this query excludes everything.
            empty={
              activeCount > 0
                ? {
                    title: 'No knowledge matches these filters',
                    description: 'Try a different type or status, or clear the search.',
                  }
                : {
                    // PRD §25, verbatim.
                    title: 'Give Concierge something to work with',
                    description:
                      'Add FAQs, policies, services, documents, and other business information.',
                    action: { label: 'Add knowledge', href: addKnowledgeHref() },
                  }
            }
          >
            {(page) => (
              <>
                <Table
                  columns={KNOWLEDGE_COLUMNS}
                  rows={page.items}
                  getRowId={(item) => item.id}
                  frame={false}
                />
                <div className="border-t border-border px-4 py-3">
                  <Pagination
                    page={page.page}
                    pageSize={page.pageSize}
                    total={page.total}
                    onPageChange={setPage}
                  />
                </div>
              </>
            )}
          </QueryBoundary>
        </Panel>
      </div>
    </div>
  )
}
