import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { Breadcrumb } from '@/components/ui/Breadcrumb'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { ConversationActionTimeline } from '@/features/conversations/ConversationActionTimeline'
import { ConversationSummaryStrip } from '@/features/conversations/ConversationSummaryStrip'
import { ConversationTranscript } from '@/features/conversations/ConversationTranscript'
import { paths } from '@/routes/paths'
import { conversationService } from '@/services/conversationService'
import type { ConversationDetail } from '@/types'

/**
 * US-3.2: the full record of one interaction.
 *
 * A missing id needs no branch of its own — the service raises a `not_found`
 * AppError carrying its own way back, and `QueryBoundary` renders it.
 */
export function ConversationDetailPage() {
  const { id = '' } = useParams()

  const query = useQuery({
    queryKey: ['conversations', id],
    queryFn: () => conversationService.get(id),
  })

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-3">
        <Breadcrumb items={[{ label: 'Conversations', href: paths.conversations }, { label: id }]} />
      </div>
      <QueryBoundary query={query} skeletonRows={8}>
        {(detail) => <ConversationDetailBody detail={detail} />}
      </QueryBoundary>
    </div>
  )
}

function ConversationDetailBody({ detail }: { detail: ConversationDetail }) {
  const { conversation, messages, actions } = detail

  return (
    <>
      <PageHeader
        title={conversation.customerName ?? 'Unknown caller'}
        description="Complete interaction record with summary, transcript, and system actions."
      />
      <div className="space-y-4">
        <ConversationSummaryStrip conversation={conversation} />
        {/*
          The prototype's `detail-layout`: what happened and what was said on
          the left, what Concierge did on the right. One column below `xl` —
          a transcript beside a timeline is unreadable much narrower.
        */}
        <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
          <div className="space-y-4">
            <Panel>
              <PanelHeader title="Summary" />
              <div className="p-4">
                {/* PRD §3.1: business language, never model or prompt detail. */}
                <p className="text-sm text-ink-secondary">
                  {conversation.summary ?? 'No summary was recorded for this conversation.'}
                </p>
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="Transcript" />
              <div className="p-4">
                <ConversationTranscript messages={messages} />
              </div>
            </Panel>
          </div>
          <Panel className="self-start">
            <PanelHeader title="Action Timeline" />
            <div className="p-4">
              <ConversationActionTimeline actions={actions} />
            </div>
          </Panel>
        </div>
      </div>
    </>
  )
}
