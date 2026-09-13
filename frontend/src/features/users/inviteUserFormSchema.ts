import { z } from 'zod'

import { ROLES } from '@/types'

/**
 * `ROLES` is declared `as const`, so zod 4 accepts it directly — no tuple cast
 * of the kind `routingRuleFormSchema` needs, whose arrays are derived `Union[]`
 * rather than const tuples.
 */
export const inviteUserFormSchema = z.object({
  name: z.string().trim().min(1, 'Enter their full name'),
  email: z
    .string()
    .trim()
    .min(1, 'Enter their email address')
    .pipe(z.email('Enter a valid email address')),
  role: z.enum(ROLES),
})

export type InviteUserFormValues = z.infer<typeof inviteUserFormSchema>

/**
 * Viewer, deliberately: an invitation should never default to more access than
 * the inviter meant to grant, and every role is one select away.
 */
export const INVITE_DEFAULTS: InviteUserFormValues = {
  name: '',
  email: '',
  role: 'viewer',
}
