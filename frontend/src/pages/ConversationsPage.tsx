import { useQuery } from '@tanstack/react-query'

import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { Pagination } from '@/components/ui/Pagination'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Table } from '@/components/ui/Table'
import { ConversationFilterBar } from '@/features/conversations/ConversationFilterBar'
import { CONVERSATION_COLUMNS } from '@/features/conversations/conversationColumns'
import { useConversationFilters } from '@/features/conversations/useConversationFilters'
import { conversationService } from '@/services/conversationService'

/**
 * US-3.1: the searchable history. Every filter, the search text and the page
 * live in the URL, so a query can be bookmarked, shared, and returned to with
 * the back button after opening a conversation.
 */
export function ConversationsPage() {
  const { state, params, activeCount, setFilter, setPage, clear } = useConversationFilters()

  const query = useQuery({
    // [namespace, entity, variable] — matches the rest of the app (e.g.
    // ['dashboard','escalations',range]) and keeps a future
    // ['conversations', id] detail query from colliding with
    // ['conversations', 'filter-options'].
    queryKey: ['conversations', 'list', params],
    queryFn: () => conversationService.list(params),
  })

  const options = useQuery({
    queryKey: ['conversations', 'filter-options'],
    queryFn: () => conversationService.listFilterOptions(),
  })

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Conversations"
        description="Search and filter every customer interaction Concierge has handled."
      />
      <div className="space-y-3">
        <ConversationFilterBar
          state={state}
          options={options.data}
          activeCount={activeCount}
          onChange={setFilter}
          onClear={clear}
        />

        {/* Loading, empty, error and success all render inside this one Panel
            so the page doesn't reflow the moment data lands — see
            RecentEscalationsCard for the same pattern. */}
        <Panel data-testid="conversations-panel">
          <QueryBoundary
            query={query}
            skeleton="table"
            skeletonRows={8}
            // Not `page.items.length === 0`: an out-of-range page (a
            // bookmarked link after the result set shrank) has an empty
            // `items` array but a non-zero `total`, and must render the
            // table shell plus a working Pagination — not tell the reader
            // nothing exists.
            isEmpty={(page) => page.total === 0}
            // Two different problems needing two different answers: nothing
            // has happened yet, versus this query excludes everything.
            empty={
              activeCount > 0
                ? {
                    title: 'No conversations match these filters',
                    description: 'Try widening the date range or clearing a filter.',
                  }
                : {
                    title: 'No conversations yet',
                    description: 'Calls and messages Concierge handles will appear here.',
                  }
            }
          >
            {(page) => (
              <>
                <Table
                  columns={CONVERSATION_COLUMNS}
                  rows={page.items}
                  getRowId={(conversation) => conversation.id}
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
