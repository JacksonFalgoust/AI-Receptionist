import { z } from 'zod'

import type { ConciergeConfiguration } from '@/types'
import type { ConciergeConfigurationPatch } from '@/services/conciergeService'

import {
  businessProfileFormSchema,
  formValuesToProfile,
  profileToFormValues,
} from './businessProfileFormSchema'
import type { BusinessProfileFormValues } from './businessProfileFormSchema'
import {
  formValuesToIdentity,
  identityFormSchema,
  identityToFormValues,
} from './identityFormSchema'
import type { IdentityFormValues } from './identityFormSchema'
import {
  formValuesToTerminology,
  terminologyFormSchema,
  terminologyToFormValues,
} from './terminologyFormSchema'
import type { TerminologyFormValues } from './terminologyFormSchema'

/**
 * The whole Configuration page shares one Save Draft / Publish pair (PRD
 * §13.4), so it shares one form: `ConfigurationPage` holds a single
 * `useForm<ConfigurationFormValues>`, and each tab's fields read their own
 * slice of it through `useFormContext`.
 */
export interface ConfigurationFormValues {
  businessProfile: BusinessProfileFormValues
  identity: IdentityFormValues
  terminology: TerminologyFormValues
}

export const configurationFormSchema = z.object({
  businessProfile: businessProfileFormSchema,
  identity: identityFormSchema,
  terminology: terminologyFormSchema,
})

export function configurationToFormValues(
  configuration: ConciergeConfiguration,
): ConfigurationFormValues {
  return {
    businessProfile: profileToFormValues(configuration.businessProfile),
    identity: identityToFormValues(configuration.identity),
    terminology: terminologyToFormValues(configuration.terminology),
  }
}

/** The submitted form, turned into what `conciergeService.saveDraft` expects. */
export function formValuesToPatch(values: ConfigurationFormValues): ConciergeConfigurationPatch {
  return {
    businessProfile: formValuesToProfile(values.businessProfile),
    identity: formValuesToIdentity(values.identity),
    terminology: formValuesToTerminology(values.terminology),
  }
}
