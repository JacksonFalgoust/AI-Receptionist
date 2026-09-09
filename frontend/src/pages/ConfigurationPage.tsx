import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { PageHeader } from '@/components/ui/PageHeader'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useToast } from '@/components/ui/ToastProvider'
import { BusinessProfileForm } from '@/features/configuration/BusinessProfileForm'
import {
  formValuesToProfile,
  profileToFormValues,
} from '@/features/configuration/businessProfileFormSchema'
import type { BusinessProfileFormValues } from '@/features/configuration/businessProfileFormSchema'
import { conciergeService } from '@/services/conciergeService'
import { toAppError } from '@/services/errors'

/**
 * This page's own query key — unrelated to `ConciergeStatusCard`'s
 * `['concierge', 'status']`. `saveDraft()` only ever changes
 * `ConciergeConfiguration`; `ConciergeStatus` (the header badge, the status
 * card) only changes on `publish()`, so there is nothing here for either to
 * invalidate.
 */
const CONFIGURATION_KEY = ['concierge', 'configuration']

/**
 * US-6.1's business profile section (C3). Identity, Terminology, Preview, and
 * the page-level Save Draft / Publish actions arrive in C4 — this section
 * saves its own draft in the meantime, the same way `KnowledgeEditorPage`
 * scopes its own mutations.
 */
export function ConfigurationPage() {
  const queryClient = useQueryClient()
  const toast = useToast()

  const query = useQuery({
    queryKey: CONFIGURATION_KEY,
    queryFn: () => conciergeService.getConfiguration(),
  })

  const save = useMutation({
    mutationFn: (values: BusinessProfileFormValues) =>
      conciergeService.saveDraft({ businessProfile: formValuesToProfile(values) }),
    onSuccess: (configuration) => {
      queryClient.setQueryData(CONFIGURATION_KEY, configuration)
      toast.show('Draft saved.', { tone: 'success' })
    },
    onError: (error) => {
      toast.show(toAppError(error).description, { tone: 'danger' })
    },
  })

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Configuration"
        description="Configure the Concierge identity and general business behavior."
      />
      <QueryBoundary query={query} skeletonRows={8}>
        {(configuration) => (
          <BusinessProfileForm
            defaultValues={profileToFormValues(configuration.businessProfile)}
            submitLabel="Save changes"
            isSubmitting={save.isPending}
            onSubmit={(values) => save.mutate(values)}
          />
        )}
      </QueryBoundary>
    </div>
  )
}
