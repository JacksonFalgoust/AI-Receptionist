import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { cn } from '@/lib/cn'
import { WORKFLOW_STEP_TYPE_LABELS } from '@/types'

import type { StepFormValues } from './workflowStepFormSchema'

export interface StepListProps {
  steps: StepFormValues[]
  selectedId: string | null
  onSelect: (id: string) => void
  onAdd: () => void
  /** Swaps the step with its neighbor. PRD §15.4 defers drag-and-drop to Phase F; this is the MVP's accessible stand-in. */
  onMove: (id: string, direction: 'up' | 'down') => void
}

/**
 * US-8.2's visual step list — the prototype's arrow-connected vertical
 * sequence. Purely presentational (no form context) so Phase F's
 * drag-and-drop builder can reuse it in place of `StepEditor` without
 * inheriting anything this component doesn't declare in its props.
 */
export function StepList({ steps, selectedId, onSelect, onAdd, onMove }: StepListProps) {
  return (
    <Panel data-testid="step-list-panel">
      <PanelHeader
        title="Steps"
        action={
          <Button size="sm" onClick={onAdd}>
            Add step
          </Button>
        }
      />
      <div className="p-4">
        {steps.length === 0 ? (
          <EmptyState
            title="No steps yet"
            description="Add a step to start building this workflow."
            action={{ label: 'Add step', onClick: onAdd }}
          />
        ) : (
          <ol className="space-y-1">
            {steps.map((step, index) => (
              <li key={step.id}>
                {index > 0 ? (
                  <div aria-hidden="true" className="py-1 text-center text-ink-muted">
                    ↓
                  </div>
                ) : null}
                <div
                  className={cn(
                    'rounded-md border',
                    step.id === selectedId
                      ? 'border-brand bg-brand/5'
                      : 'border-border bg-surface',
                  )}
                >
                  <button
                    type="button"
                    aria-current={step.id === selectedId ? 'true' : undefined}
                    onClick={() => onSelect(step.id)}
                    className={cn(
                      'w-full px-3 py-2 text-left text-sm',
                      step.id !== selectedId && 'hover:bg-canvas-tint',
                    )}
                  >
                    <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      {WORKFLOW_STEP_TYPE_LABELS[step.type]}
                    </span>
                    <div className="font-medium text-ink">{step.name || 'Untitled step'}</div>
                    {step.description ? (
                      <p className="mt-0.5 text-xs text-ink-secondary">{step.description}</p>
                    ) : null}
                  </button>
                  {steps.length > 1 ? (
                    <div className="flex justify-end gap-1 border-t border-border px-2 py-1">
                      {index > 0 ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Move ${step.name || 'this step'} up`}
                          onClick={() => onMove(step.id, 'up')}
                        >
                          ↑
                        </Button>
                      ) : null}
                      {index < steps.length - 1 ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Move ${step.name || 'this step'} down`}
                          onClick={() => onMove(step.id, 'down')}
                        >
                          ↓
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </Panel>
  )
}
