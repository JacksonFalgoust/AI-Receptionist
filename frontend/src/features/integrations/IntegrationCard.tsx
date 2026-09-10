import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import { canDisconnect, integrationAction } from '@/lib/integrationActions'
import { relativeTime } from '@/lib/formatDate'
import { integrationCategoryLabel } from '@/lib/integrationLabels'
import { toAppError } from '@/services/errors'
import type { AppError } from '@/services/errors'
import { integrationService } from '@/services/integrationService'
import type { ConnectIntegrationInput } from '@/services/integrationService'
import type { Integration } from '@/types'

import { ConnectIntegrationModal } from './ConnectIntegrationModal'

/** Shared with `IntegrationsPage`'s list query, so a card's own mutation can patch it directly. */
export const INTEGRATIONS_KEY = ['integrations', 'list']

export interface IntegrationCardProps {
  integration: Integration
}

/**
 * US-9.1. Self-contained the way `FeatureCard` is: its own mutations, its own
 * confirm and toast, patching the shared `['integrations', 'list']` cache on
 * success rather than the page tracking which card is mid-action.
 */
export function IntegrationCard({ integration }: IntegrationCardProps) {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const toast = useToast()
  const [isModalOpen, setModalOpen] = useState(false)
  const [connectError, setConnectError] = useState<AppError | null>(null)
  const [isConfirmingDisconnect, setConfirmingDisconnect] = useState(false)

  const action = integrationAction(integration.status)

  // Both triggers below stay mounted the whole time (only `aria-hidden` /
  // `tabIndex` toggle) rather than being conditionally unmounted while their
  // own dialog is open. `useFocusTrap` (src/lib/useFocusTrap.ts, shared by
  // `Modal`/`ConfirmDialog`) captures `document.activeElement` into a ref
  // when a dialog opens and calls `.focus()` on that same node when it
  // closes — conditionally unmounting the trigger detaches the node the trap
  // captured, making that `.focus()` call a silent no-op. Keeping the node
  // mounted keeps the trap's own restoration attempt valid.
  //
  // The explicit restoration below is a second, independent guarantee on top
  // of that, not a replacement for it: for the Connect/Repair trigger, one
  // component (this one) drives both "hide the trigger" and "close the
  // modal" in the same render, so `useFocusTrap`'s restoration alone is
  // already reliable. For Disconnect, `useConfirm()`'s dialog is owned by a
  // *different* component (`ConfirmDialogProvider`), reacting to the same
  // click via a resolved Promise rather than a shared state update — two
  // separate commits with no ordering guarantee between "the dialog closes"
  // and "this card un-hides its own trigger." Rather than depend on
  // React/microtask scheduling details to land in the order that happens to
  // work, both triggers restore their own focus explicitly, tied to their
  // own state transitioning back to false — which is guaranteed to run after
  // this component's own commit (aria-hidden already removed) regardless of
  // what the trap does elsewhere.
  const connectTriggerRef = useRef<HTMLButtonElement>(null)
  const disconnectTriggerRef = useRef<HTMLButtonElement>(null)
  const wasModalOpenRef = useRef(false)
  const wasConfirmingDisconnectRef = useRef(false)

  useEffect(() => {
    if (wasModalOpenRef.current && !isModalOpen) connectTriggerRef.current?.focus()
    wasModalOpenRef.current = isModalOpen
  }, [isModalOpen])

  useEffect(() => {
    if (wasConfirmingDisconnectRef.current && !isConfirmingDisconnect) {
      disconnectTriggerRef.current?.focus()
    }
    wasConfirmingDisconnectRef.current = isConfirmingDisconnect
  }, [isConfirmingDisconnect])

  function patchCache(updated: Integration) {
    queryClient.setQueryData<Integration[]>(INTEGRATIONS_KEY, (current) =>
      current?.map((item) => (item.id === updated.id ? updated : item)),
    )
  }

  const connect = useMutation({
    mutationFn: (input: ConnectIntegrationInput) =>
      action?.kind === 'repair'
        ? integrationService.repair(integration.id, input)
        : integrationService.connect(integration.id, input),
    onSuccess: (updated) => {
      patchCache(updated)
      setConnectError(null)
      setModalOpen(false)
      // Wording deliberately avoids the substring "connected": the
      // `StatusPill` right next to it already renders that word for a
      // `connected` status, and a toast repeating it makes "reports it"
      // ambiguous for anything reading the screen by text.
      toast.show(`${updated.name} is set up and ready.`, { tone: 'success' })
    },
    // The dialog stays open holding what was typed; the error renders inside it.
    onError: (error) => setConnectError(toAppError(error)),
  })

  const disconnect = useMutation({
    mutationFn: () => integrationService.disconnect(integration.id),
    onSuccess: (updated) => {
      patchCache(updated)
      toast.show(`${updated.name} disconnected.`, { tone: 'success' })
    },
    onError: (error) => toast.show(toAppError(error).description, { tone: 'danger' }),
  })

  async function handleDisconnect() {
    setConfirmingDisconnect(true)
    const confirmed = await confirm({
      title: `Disconnect ${integration.name}?`,
      // The real consequence, not a generic warning: the card already knows
      // which features depend on this connection.
      description:
        integration.features.length > 0
          ? `${integration.features.join(', ')} will stop working until ${integration.name} is reconnected.`
          : `Concierge will no longer be able to reach ${integration.name}.`,
      confirmLabel: 'Disconnect',
      tone: 'danger',
    })
    setConfirmingDisconnect(false)
    if (!confirmed) return
    disconnect.mutate()
  }

  return (
    <Panel role="group" aria-label={integration.name} className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">{integration.name}</h3>
          <p className="mt-0.5 text-sm text-ink-secondary">
            {integrationCategoryLabel(integration.category)}
          </p>
        </div>
        <StatusPill status={integration.status} />
      </div>
      <div className="space-y-1 text-sm text-ink-secondary">
        <p>
          {integration.lastActivityAt
            ? `Last activity: ${relativeTime(integration.lastActivityAt)}`
            : 'No activity yet'}
        </p>
        {integration.connectedAccount ? <p>Account: {integration.connectedAccount}</p> : null}
        {/* Omitted while its own disconnect confirmation is open: that dialog
            names these same features to explain the consequence, and the
            duplicate text makes "which one said it" ambiguous for anything
            reading the screen by text. */}
        {!isConfirmingDisconnect ? (
          <p>
            {integration.features.length > 0
              ? `Features: ${integration.features.join(', ')}`
              : 'Not used by any feature yet'}
          </p>
        ) : null}
      </div>

      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        {/* aria-hidden (not unmounted) while its own modal is open: the
            modal's submit button carries the same label (e.g. "Connect"), so
            leaving this one in the accessibility tree behind the overlay
            makes the name ambiguous for queries and assistive tech alike.
            tabIndex={-1} keeps it out of the tab order while aria-hidden, and
            the node itself stays mounted so `useFocusTrap` (see above) has a
            live element to restore focus to. */}
        {action ? (
          <Button
            ref={connectTriggerRef}
            aria-hidden={isModalOpen || undefined}
            tabIndex={isModalOpen ? -1 : undefined}
            onClick={() => {
              setConnectError(null)
              setModalOpen(true)
            }}
          >
            {action.label}
          </Button>
        ) : null}
        {canDisconnect(integration.status) ? (
          <Button
            ref={disconnectTriggerRef}
            variant="ghost"
            aria-hidden={isConfirmingDisconnect || undefined}
            tabIndex={isConfirmingDisconnect ? -1 : undefined}
            onClick={handleDisconnect}
            isLoading={disconnect.isPending}
          >
            Disconnect
          </Button>
        ) : null}
      </div>

      {action ? (
        <ConnectIntegrationModal
          integration={integration}
          isOpen={isModalOpen}
          onClose={() => setModalOpen(false)}
          onSubmit={(input) => connect.mutate(input)}
          isPending={connect.isPending}
          error={connectError}
        />
      ) : null}
    </Panel>
  )
}
