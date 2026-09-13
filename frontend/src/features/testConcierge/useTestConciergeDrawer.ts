import { useContext } from 'react'

import { TestConciergeDrawerContext } from './TestConciergeDrawerContext'
import type { TestConciergeDrawerContextValue } from './TestConciergeDrawerContext'

export function useTestConciergeDrawer(): TestConciergeDrawerContextValue {
  const ctx = useContext(TestConciergeDrawerContext)
  if (!ctx) {
    throw new Error('useTestConciergeDrawer must be used within a TestConciergeDrawerProvider')
  }
  return ctx
}
