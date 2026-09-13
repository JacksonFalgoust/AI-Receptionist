import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { TestConciergePanel } from '@/features/testConcierge/TestConciergePanel'

/**
 * US-13.1 / PRD §22. The same content the header drawer shows — this route
 * exists so the PRD's recommended `/test` route stays a real destination,
 * not a stub, once the drawer replaces its own former Link to here.
 */
export function TestPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Test Concierge"
        description="Simulate an interaction without affecting production customers."
      />
      <Panel className="flex h-[32rem] flex-col p-4">
        <TestConciergePanel />
      </Panel>
    </div>
  )
}
