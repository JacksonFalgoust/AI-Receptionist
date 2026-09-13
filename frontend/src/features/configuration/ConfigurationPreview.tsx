import { Button } from '@/components/ui/Button'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { useAuth } from '@/features/auth/useAuth'
import { useTestConciergeDrawer } from '@/features/testConcierge/useTestConciergeDrawer'
import { can } from '@/lib/permissions'
import type { ConciergeIdentity } from '@/types'

export interface ConfigurationPreviewProps {
  identity: ConciergeIdentity
}

/**
 * US-6.1's Preview tab. Reads the last-saved identity rather than the form's
 * live, possibly-unsaved values — this shows what Concierge will actually
 * say, not a draft-in-progress; save the draft first to preview an edit.
 * No audio: that needs GuideAnts' TTS, which isn't wired up until E6.
 */
export function ConfigurationPreview({ identity }: ConfigurationPreviewProps) {
  const { user } = useAuth()
  const { open } = useTestConciergeDrawer()

  return (
    <div className="max-w-2xl space-y-4">
      <Panel>
        <PanelHeader title="Greeting" />
        <div className="p-4 text-sm text-ink">{identity.greeting}</div>
      </Panel>
      <Panel>
        <PanelHeader title="Closing message" />
        <div className="p-4 text-sm text-ink">{identity.closing}</div>
      </Panel>
      {user && can(user.role, 'use:test') ? (
        <Button variant="primary" onClick={open}>
          Test Concierge
        </Button>
      ) : null}
    </div>
  )
}
