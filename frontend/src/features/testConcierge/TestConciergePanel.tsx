import { useState } from 'react'
import type { FormEvent } from 'react'

import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ChatBubble } from '@/components/ui/ChatBubble'
import { EmptyState } from '@/components/ui/EmptyState'
import { Textarea } from '@/components/ui/Textarea'
import { formatDateTime } from '@/lib/formatDate'
import { toAppError } from '@/services/errors'
import type { TestConciergeTurn } from '@/types'

import { useTestConciergeDrawer } from './useTestConciergeDrawer'

interface UsedRow {
  label: string
  value: string
}

/** Only the fields a turn actually populated — an empty row is worse than no row. */
function usedRows(turn: TestConciergeTurn): UsedRow[] {
  const rows: UsedRow[] = []
  if (turn.workflowUsed) rows.push({ label: 'Workflow', value: turn.workflowUsed })
  if (turn.knowledgeUsed?.length) {
    rows.push({ label: 'Knowledge', value: turn.knowledgeUsed.join(', ') })
  }
  if (turn.integrationsUsed?.length) {
    rows.push({ label: 'Integrations', value: turn.integrationsUsed.join(', ') })
  }
  if (turn.actionsExecuted?.length) {
    rows.push({ label: 'Actions', value: turn.actionsExecuted.join(', ') })
  }
  return rows
}

/**
 * Shared by `TestConciergeDrawer` and `TestPage`, so the PRD §22 `/test`
 * route keeps rendering real content rather than a stub. Reads
 * `useTestConciergeDrawer()` directly rather than taking props — both call
 * sites share the same context, so there is exactly one place a
 * customer/concierge exchange is rendered.
 */
export function TestConciergePanel() {
  const { turns, pendingMessage, isSending, send, clear } = useTestConciergeDrawer()
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  const canSend = value.trim().length > 0 && !isSending

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const message = value.trim()
    if (!message) return
    setError(null)
    try {
      await send(message)
      setValue('')
    } catch (submitError) {
      setError(toAppError(submitError).description)
    }
  }

  const isEmpty = turns.length === 0 && !pendingMessage

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <Badge tone="warning">TEST MODE</Badge>
        <p className="mt-1 text-xs text-ink-secondary">
          Messages here don't reach real customers.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <EmptyState
            title="Test your Concierge"
            description="Send a message to try out your Concierge."
          />
        ) : (
          <div className="flex flex-col gap-2">
            {turns.map((turn) => {
              const rows = usedRows(turn)
              return (
                <div key={turn.id} className="flex flex-col gap-1">
                  <ChatBubble speaker="customer" message={turn.customerMessage} />
                  <ChatBubble
                    speaker="concierge"
                    message={turn.reply}
                    time={formatDateTime(turn.createdAt)}
                  />
                  {rows.length > 0 ? (
                    <details className="max-w-[75%] self-end">
                      <summary className="cursor-pointer text-xs font-semibold text-ink-secondary hover:text-ink">
                        What the Concierge used
                      </summary>
                      <dl className="mt-1 space-y-0.5 text-xs text-ink-secondary">
                        {rows.map((row) => (
                          <div key={row.label}>
                            <dt className="inline font-semibold">{row.label}: </dt>
                            <dd className="inline">{row.value}</dd>
                          </div>
                        ))}
                      </dl>
                    </details>
                  ) : null}
                </div>
              )
            })}
            {pendingMessage ? <ChatBubble speaker="customer" message={pendingMessage} /> : null}
          </div>
        )}
      </div>

      {error ? (
        <Alert tone="danger" title="The Concierge could not reply" description={error} />
      ) : null}

      <form onSubmit={onSubmit} className="flex flex-col gap-2 border-t border-border pt-3">
        <Textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Type a message as if you were a customer…"
          rows={2}
          aria-label="Message"
          disabled={isSending}
        />
        <div className="flex items-center justify-between gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              clear()
              setError(null)
            }}
            disabled={turns.length === 0}
          >
            Clear conversation
          </Button>
          <Button type="submit" size="sm" isLoading={isSending} disabled={!canSend}>
            Send
          </Button>
        </div>
      </form>
    </div>
  )
}
