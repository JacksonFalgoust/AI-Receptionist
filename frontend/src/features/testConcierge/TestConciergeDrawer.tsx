import { Drawer } from '@/components/ui/Drawer'

import { TestConciergePanel } from './TestConciergePanel'
import { useTestConciergeDrawer } from './useTestConciergeDrawer'

/**
 * Escape-to-close, backdrop-close, and focus trapping all come from `Drawer`
 * itself — nothing new needed here, the same free ride D2's modals and E1's
 * confirm dialogs got.
 */
export function TestConciergeDrawer() {
  const { isOpen, close } = useTestConciergeDrawer()
  return (
    <Drawer isOpen={isOpen} onClose={close} title="Test Concierge">
      <TestConciergePanel />
    </Drawer>
  )
}
