import { cn } from '@/lib/cn'
import type { SemanticTone } from '@/lib/statusTone'
import { TONE_CLASSES } from '@/lib/statusTone'
import { Button } from './Button'

export interface AlertAction {
  label: string
  onClick: () => void
}

export interface AlertProps {
  tone: Exclude<SemanticTone, 'muted'>
  title: string
  description?: string
  actions?: AlertAction[]
}

export function Alert({ tone, title, description, actions }: AlertProps) {
  return (
    <div role="alert" className={cn('rounded-md border border-current/20 px-4 py-3', TONE_CLASSES[tone])}>
      <p className="text-sm font-semibold">{title}</p>
      {description ? <p className="mt-1 text-sm">{description}</p> : null}
      {actions?.length ? (
        <div className="mt-2 flex gap-2">
          {actions.map((action) => (
            <Button key={action.label} variant="ghost" size="sm" onClick={action.onClick}>
              {action.label}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
