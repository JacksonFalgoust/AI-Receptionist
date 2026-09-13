import { useFormContext } from 'react-hook-form'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { useAuth } from '@/features/auth/useAuth'
import { useTestConciergeDrawer } from '@/features/testConcierge/useTestConciergeDrawer'
import { LANGUAGE_OPTIONS } from '@/lib/languages'
import { can } from '@/lib/permissions'
import { withCurrentValue, withCurrentValues } from '@/lib/selectOptions'
import { VOICE_OPTIONS } from '@/lib/voices'
import type { Tone } from '@/types'

import type { ConfigurationFormValues } from './configurationFormSchema'

const TONE_OPTIONS: { value: Tone; label: string }[] = [
  { value: 'professional', label: 'Professional' },
  { value: 'friendly', label: 'Friendly' },
  { value: 'casual', label: 'Casual' },
  { value: 'formal', label: 'Formal' },
  { value: 'custom', label: 'Custom' },
]

export interface IdentityFieldsProps {
  /** Switches the page to the Preview tab — this component owns no tab state itself. */
  onPreviewGreeting: () => void
}

/**
 * US-6.1's Concierge identity fields — the Identity slice of the
 * Configuration page's single shared form (see `BusinessProfileFields` for
 * the same split rationale).
 */
export function IdentityFields({ onPreviewGreeting }: IdentityFieldsProps) {
  const { user } = useAuth()
  const { open } = useTestConciergeDrawer()
  const {
    register,
    watch,
    formState: { errors },
  } = useFormContext<ConfigurationFormValues>()

  const tone = watch('identity.tone')
  const voice = watch('identity.voice')
  const primaryLanguage = watch('identity.primaryLanguage')
  const supportedLanguages = watch('identity.supportedLanguages') ?? []
  const identityErrors = errors.identity
  const languageOptions = withCurrentValues(LANGUAGE_OPTIONS, supportedLanguages)

  return (
    <div className="max-w-2xl space-y-1">
      <Field
        label="Concierge name"
        htmlFor="identityName"
        error={identityErrors?.name?.message}
      >
        <Input {...register('identity.name')} />
      </Field>

      <Field label="Greeting" htmlFor="greeting" error={identityErrors?.greeting?.message}>
        <Textarea rows={3} {...register('identity.greeting')} />
      </Field>

      <Field label="Closing message" htmlFor="closing" error={identityErrors?.closing?.message}>
        <Textarea rows={3} {...register('identity.closing')} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Voice" htmlFor="voice" error={identityErrors?.voice?.message}>
          <Select
            {...register('identity.voice')}
            options={withCurrentValue(VOICE_OPTIONS, voice)}
            placeholder="Select a voice"
          />
        </Field>
        <Field label="Tone" htmlFor="tone" error={identityErrors?.tone?.message}>
          <Select
            {...register('identity.tone')}
            options={TONE_OPTIONS}
            placeholder="Select a tone"
          />
        </Field>
      </div>

      {tone === 'custom' ? (
        <Field
          label="Custom tone description"
          htmlFor="customTone"
          error={identityErrors?.customTone?.message}
        >
          <Input {...register('identity.customTone')} />
        </Field>
      ) : null}

      <Field
        label="Primary language"
        htmlFor="primaryLanguage"
        error={identityErrors?.primaryLanguage?.message}
      >
        <Select
          {...register('identity.primaryLanguage')}
          options={withCurrentValue(LANGUAGE_OPTIONS, primaryLanguage)}
          placeholder="Select a language"
        />
      </Field>

      <fieldset className="mb-4">
        <legend className="mb-1.5 block text-sm font-semibold text-ink">
          Supported languages
        </legend>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {languageOptions.map((option) => (
            <label key={option.value} className="inline-flex items-center gap-1.5 text-sm text-ink">
              <input
                type="checkbox"
                value={option.value}
                {...register('identity.supportedLanguages')}
              />
              {option.label}
            </label>
          ))}
        </div>
        {identityErrors?.supportedLanguages?.message ? (
          <p role="alert" className="mt-1.5 text-xs text-danger">
            {identityErrors.supportedLanguages.message}
          </p>
        ) : null}
      </fieldset>

      <div className="flex gap-2">
        <Button type="button" variant="ghost" onClick={onPreviewGreeting}>
          Preview greeting
        </Button>
        {user && can(user.role, 'use:test') ? (
          <Button type="button" variant="primary" onClick={open}>
            Test Concierge
          </Button>
        ) : null}
      </div>
    </div>
  )
}
