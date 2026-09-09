import { useParams } from 'react-router-dom'

import { PlaceholderPage } from '@/components/common/PlaceholderPage'

/**
 * US-5.2's editor. C1 (US-5.1) links every add action and every row's Edit
 * here, so the library's controls are real navigation from the day it ships;
 * C2 replaces this stub with the form itself.
 */
export function KnowledgeEditorPage() {
  const { id } = useParams()
  const isNew = id === undefined

  return (
    <PlaceholderPage
      eyebrow="Concierge"
      title={isNew ? 'Add knowledge' : 'Edit knowledge'}
      description={
        isNew
          ? 'Add information Concierge can use when responding to customers.'
          : 'Update this information so Concierge answers with what is true today.'
      }
      story="US-5.2"
    />
  )
}
