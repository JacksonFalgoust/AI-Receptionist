import { useContext } from 'react'

import { ConfirmContext } from './ConfirmDialog'
import type { ConfirmOptions } from './ConfirmDialog'

export function useConfirm(): (options: ConfirmOptions) => Promise<boolean> {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used within a ConfirmDialogProvider')
  return ctx.confirm
}
