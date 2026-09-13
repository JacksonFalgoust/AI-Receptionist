import type { Permission } from '@/lib/permissions'
import { paths } from '@/routes/paths'

/**
 * Every action here is a real, navigable URL — an in-app path or a
 * `mailto:` link — never an `onClick`, so there is nothing to discriminate
 * between the way `EmptyStateAction` discriminates `href` from `onClick`.
 */
export interface HelpResourceAction {
  label: string
  href: string
  /** Omitted entirely (not just disabled) for a role that lacks this. */
  permission?: Permission
}

export interface HelpResource {
  title: string
  description: string
  action?: HelpResourceAction
}

/**
 * US-14.1 / PRD §23. Static UI copy, not a domain record — no service, no
 * mock seed. Copy is taken verbatim from the prototype (`help.html`) except
 * "Contact support"'s CTA, which the prototype leaves as a button with no
 * destination; a `mailto:` link is a real, working action with no backend
 * needed, following the "no button that does nothing" rule D2 and C6
 * already established in this codebase.
 */
export const HELP_RESOURCES: HelpResource[] = [
  {
    title: 'Getting started',
    description: 'Complete setup, test Concierge, and go live with confidence.',
    action: {
      label: 'Open configuration',
      href: paths.configuration,
      permission: 'manage:configuration',
    },
  },
  {
    title: 'Configuration guides',
    description: 'Identity, hours, terminology, and publish workflow.',
  },
  {
    title: 'Integration guides',
    description: 'Connect CRM, scheduling, payments, and custom tools.',
    action: {
      label: 'View integrations',
      href: paths.integrations,
      permission: 'manage:integrations',
    },
  },
  {
    title: 'Contact support',
    description: 'Reach GuideAnts support for account or product help.',
    action: { label: 'Contact support', href: 'mailto:support@guideants.example' },
  },
]
