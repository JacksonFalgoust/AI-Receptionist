import { ChevronDown, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button, buttonClasses } from '@/components/ui/Button'
import { Dropdown } from '@/components/ui/Dropdown'
import { paths } from '@/routes/paths'
import type { KnowledgeType } from '@/types'

export interface AddKnowledgeAction {
  label: string
  /**
   * Preselects the editor's Type. `undefined` deliberately leaves it open —
   * six actions cannot cover ten types, so "Add business information" is what
   * keeps procedure, product, service, pricing and location reachable.
   */
  type?: KnowledgeType
}

/** PRD §16.3, in the order the PRD lists them. */
export const ADD_KNOWLEDGE_ACTIONS: AddKnowledgeAction[] = [
  { label: 'Create FAQ', type: 'faq' },
  { label: 'Add text', type: 'instruction' },
  { label: 'Upload document', type: 'document' },
  { label: 'Add URL', type: 'url' },
  { label: 'Create policy', type: 'policy' },
  { label: 'Add business information' },
]

export function addKnowledgeHref(type?: KnowledgeType): string {
  return type ? `${paths.knowledgeNew}?type=${type}` : paths.knowledgeNew
}

const UPLOAD_ACTION = ADD_KNOWLEDGE_ACTIONS.find((action) => action.type === 'document')!

/**
 * US-5.1's add actions. All six sit together under one primary trigger so the
 * full set is discoverable in one place; uploading is additionally promoted to
 * a shortcut, as in the prototype, because it is the one people arrive
 * intending to do.
 */
export function AddKnowledgeMenu() {
  return (
    <>
      <Link
        to={addKnowledgeHref(UPLOAD_ACTION.type)}
        className={buttonClasses('ghost', 'md')}
      >
        <Upload className="h-4 w-4" aria-hidden />
        {UPLOAD_ACTION.label}
      </Link>

      <Dropdown
        align="end"
        trigger={
          <Button trailingIcon={<ChevronDown className="h-4 w-4" aria-hidden />}>
            Add knowledge
          </Button>
        }
      >
        {ADD_KNOWLEDGE_ACTIONS.map((action) => (
          <Link
            key={action.label}
            role="menuitem"
            to={addKnowledgeHref(action.type)}
            className="block rounded-sm px-3 py-2 text-sm text-ink hover:bg-canvas-tint"
          >
            {action.label}
          </Link>
        ))}
      </Dropdown>
    </>
  )
}
