import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormProvider, useForm } from 'react-hook-form'

import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Tabs } from '@/components/ui/Tabs'
import type { TabItem } from '@/components/ui/Tabs'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import { BusinessProfileFields } from '@/features/configuration/BusinessProfileFields'
import { ConfigurationPreview } from '@/features/configuration/ConfigurationPreview'
import {
  configurationFormSchema,
  configurationToFormValues,
  formValuesToPatch,
} from '@/features/configuration/configurationFormSchema'
import type { ConfigurationFormValues } from '@/features/configuration/configurationFormSchema'
import { IdentityFields } from '@/features/configuration/IdentityFields'
import { TerminologyFields } from '@/features/configuration/TerminologyFields'
import { conciergeService } from '@/services/conciergeService'
import { toAppError } from '@/services/errors'
import type { ConciergeConfiguration } from '@/types'

const CONFIGURATION_KEY = ['concierge', 'configuration']

type ConfigurationTab = 'businessProfile' | 'identity' | 'terminology' | 'preview'

const TAB_LABELS: Record<ConfigurationTab, string> = {
  businessProfile: 'Business profile',
  identity: 'Identity',
  terminology: 'Terminology',
  preview: 'Preview',
}

const TAB_ORDER: ConfigurationTab[] = ['businessProfile', 'identity', 'terminology', 'preview']

/**
 * US-6.1 (C4): Identity, Terminology, and Preview join C3's Business profile
 * under one set of tabs, one shared form, and one Save Draft / Publish pair
 * (PRD §13.4) — saving a draft never publishes it; only Publish does, and
 * only after confirmation.
 */
export function ConfigurationPage() {
  const query = useQuery({
    queryKey: CONFIGURATION_KEY,
    queryFn: () => conciergeService.getConfiguration(),
  })

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Configuration"
        description="Configure the Concierge identity and general business behavior."
      />
      <QueryBoundary query={query} skeletonRows={8}>
        {(configuration) => <ConfigurationForm configuration={configuration} />}
      </QueryBoundary>
    </div>
  )
}

function ConfigurationForm({ configuration }: { configuration: ConciergeConfiguration }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [activeTab, setActiveTab] = useState<ConfigurationTab>('businessProfile')

  const form = useForm<ConfigurationFormValues>({
    defaultValues: configurationToFormValues(configuration),
    resolver: zodResolver(configurationFormSchema),
  })
  const { errors } = form.formState

  const save = useMutation({
    mutationFn: async ({
      values,
      thenPublish,
    }: {
      values: ConfigurationFormValues
      thenPublish: boolean
    }) => {
      // Publish always saves what's on screen first — nobody wants an edit
      // to look published when it was actually last session's stale draft.
      const saved = await conciergeService.saveDraft(formValuesToPatch(values))
      return thenPublish ? conciergeService.publish() : saved
    },
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(CONFIGURATION_KEY, updated)
      form.reset(configurationToFormValues(updated))
      if (variables.thenPublish) {
        // Only publish() changes ConciergeStatus.lastConfigurationChangeAt —
        // saveDraft() alone has nothing for the header badge to refetch.
        queryClient.invalidateQueries({ queryKey: ['concierge', 'status'] })
        toast.show('Configuration published.', { tone: 'success' })
      } else {
        toast.show('Draft saved.', { tone: 'success' })
      }
    },
    onError: (error) => {
      toast.show(toAppError(error).description, { tone: 'danger' })
    },
  })

  // Every section shares this one validated form (PRD §13.4's single Save
  // Draft / Publish pair), so a validation error anywhere blocks both
  // actions — including on a tab the user isn't currently viewing, where the
  // only other cue is the tab's own red dot. Without this, clicking Save
  // Draft or Publish while that's true does nothing visible at all.
  function onInvalid() {
    toast.show('Fix the highlighted tab before saving.', { tone: 'danger' })
  }

  const handleSaveDraft = form.handleSubmit((values) => {
    save.mutate({ values, thenPublish: false })
  }, onInvalid)

  const handlePublish = form.handleSubmit(async (values) => {
    const confirmed = await confirm({
      title: 'Publish these changes?',
      description: 'Concierge will immediately use this configuration for new conversations.',
      confirmLabel: 'Publish',
    })
    if (!confirmed) return
    save.mutate({ values, thenPublish: true })
  }, onInvalid)

  const isSavingDraft = save.isPending && save.variables?.thenPublish === false
  const isPublishing = save.isPending && save.variables?.thenPublish === true

  // 'preview' has no slice of its own in `errors` — it previews the last
  // saved identity rather than editing anything.
  const tabItems: TabItem[] = TAB_ORDER.map((value) => ({
    value,
    label: TAB_LABELS[value],
    hasError: value !== 'preview' && Boolean(errors[value]),
  }))

  return (
    <FormProvider {...form}>
      <div className="mb-4 flex justify-end gap-2">
        <Button
          variant="ghost"
          type="button"
          isLoading={isSavingDraft}
          disabled={save.isPending}
          onClick={handleSaveDraft}
        >
          Save draft
        </Button>
        <Button
          type="button"
          isLoading={isPublishing}
          disabled={save.isPending}
          onClick={handlePublish}
        >
          Publish changes
        </Button>
      </div>
      {configuration.hasUnpublishedChanges ? (
        <div className="mb-4">
          <Alert
            tone="info"
            title="This configuration has draft changes that have not been published yet."
            description="Publish when you are ready for Concierge to use them."
          />
        </div>
      ) : null}
      <div>
        <Tabs
          items={tabItems}
          value={activeTab}
          onChange={(value) => setActiveTab(value as ConfigurationTab)}
        >
          {activeTab === 'businessProfile' ? <BusinessProfileFields /> : null}
          {activeTab === 'identity' ? (
            <IdentityFields onPreviewGreeting={() => setActiveTab('preview')} />
          ) : null}
          {activeTab === 'terminology' ? <TerminologyFields /> : null}
          {activeTab === 'preview' ? (
            <ConfigurationPreview identity={configuration.identity} />
          ) : null}
        </Tabs>
      </div>
    </FormProvider>
  )
}
