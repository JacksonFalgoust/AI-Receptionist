import { z } from 'zod'

import type { ConciergeIdentity, Tone } from '@/types'

export interface IdentityFormValues {
  name: string
  greeting: string
  closing: string
  voice: string
  tone: Tone | ''
  /** Only meaningful when `tone === 'custom'`. */
  customTone: string
  primaryLanguage: string
  supportedLanguages: string[]
}

export const identityFormSchema = z
  .object({
    name: z.string().trim().min(1, 'Enter a Concierge name'),
    greeting: z.string().trim().min(1, 'Enter a greeting'),
    closing: z.string().trim().min(1, 'Enter a closing message'),
    voice: z.string().trim().min(1, 'Select a voice'),
    // See knowledgeFormSchema's `type` field for why this is z.custom rather
    // than a plain z.string(): it keeps the inferred type `Tone | ''` in sync
    // with `IdentityFormValues` for `useForm`'s resolver to type-check.
    tone: z.custom<Tone | ''>((value) => typeof value === 'string'),
    customTone: z.string(),
    primaryLanguage: z.string().trim().min(1, 'Select a primary language'),
    supportedLanguages: z.array(z.string()),
  })
  .superRefine((values, ctx) => {
    if (values.tone === '') {
      ctx.addIssue({ code: 'custom', path: ['tone'], message: 'Select a tone' })
    } else if (values.tone === 'custom' && values.customTone.trim() === '') {
      ctx.addIssue({
        code: 'custom',
        path: ['customTone'],
        message: 'Describe the custom tone',
      })
    }

    if (values.supportedLanguages.length === 0) {
      ctx.addIssue({
        code: 'custom',
        path: ['supportedLanguages'],
        message: 'Select at least one supported language',
      })
    } else if (
      values.primaryLanguage.trim() !== '' &&
      !values.supportedLanguages.includes(values.primaryLanguage.trim())
    ) {
      ctx.addIssue({
        code: 'custom',
        path: ['supportedLanguages'],
        message: 'Supported languages must include the primary language',
      })
    }
  })

/** An existing identity's fields, laid out as the form's controls expect them. */
export function identityToFormValues(identity: ConciergeIdentity): IdentityFormValues {
  return {
    name: identity.name,
    greeting: identity.greeting,
    closing: identity.closing,
    voice: identity.voice,
    tone: identity.tone,
    customTone: identity.customTone ?? '',
    primaryLanguage: identity.primaryLanguage,
    supportedLanguages: identity.supportedLanguages,
  }
}

/** The submitted form, turned into what `conciergeService.saveDraft` expects. */
export function formValuesToIdentity(values: IdentityFormValues): ConciergeIdentity {
  const tone = values.tone as Tone

  return {
    name: values.name.trim(),
    greeting: values.greeting.trim(),
    closing: values.closing.trim(),
    voice: values.voice.trim(),
    tone,
    // Only a custom tone has a description to save — carrying one across for
    // any other preset would just be a stale value nothing reads.
    customTone: tone === 'custom' ? values.customTone.trim() : undefined,
    primaryLanguage: values.primaryLanguage.trim(),
    supportedLanguages: values.supportedLanguages,
  }
}
