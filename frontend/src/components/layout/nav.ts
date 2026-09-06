import {
  Activity,
  BookOpen,
  ChartColumn,
  CircleHelp,
  CreditCard,
  GitBranch,
  House,
  LayoutGrid,
  MessageSquare,
  Plug,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  type LucideIcon,
} from 'lucide-react'

import type { Permission } from '@/lib/permissions'
import { paths } from '@/routes/paths'

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  /** Hidden from the sidebar when the signed-in role lacks this. */
  permission: Permission
}

export interface NavGroup {
  /** Undefined for the ungrouped top-level item (Overview). */
  label?: string
  items: NavItem[]
}

/**
 * Sidebar structure from PRD §5, with the Concierge group ordered
 * Knowledge → Configuration → Features → Workflows per USER_STORIES.
 *
 * Live Activity (`paths.activity`) and Security & Audit (`paths.security`) are
 * deliberately absent: both are out of MVP scope. Their routes exist, so
 * adding them here is all that Phase F requires.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    items: [
      {
        label: 'Overview',
        to: paths.overview,
        icon: House,
        permission: 'view:overview',
      },
    ],
  },
  {
    label: 'Operations',
    items: [
      {
        label: 'Conversations',
        to: paths.conversations,
        icon: MessageSquare,
        permission: 'view:conversations',
      },
      {
        label: 'Analytics',
        to: paths.analytics,
        icon: ChartColumn,
        permission: 'view:analytics',
      },
    ],
  },
  {
    label: 'Concierge',
    items: [
      {
        label: 'Knowledge',
        to: paths.knowledge,
        icon: BookOpen,
        permission: 'manage:knowledge',
      },
      {
        label: 'Configuration',
        to: paths.configuration,
        icon: SlidersHorizontal,
        permission: 'manage:configuration',
      },
      {
        label: 'Features',
        to: paths.features,
        icon: LayoutGrid,
        permission: 'manage:features',
      },
      {
        label: 'Workflows',
        to: paths.workflows,
        icon: GitBranch,
        permission: 'manage:workflows',
      },
    ],
  },
  {
    label: 'Connect',
    items: [
      {
        label: 'Integrations',
        to: paths.integrations,
        icon: Plug,
        permission: 'manage:integrations',
      },
      {
        label: 'Escalation & Routing',
        to: paths.routing,
        icon: Route,
        permission: 'manage:routing',
      },
    ],
  },
  {
    label: 'Administration',
    items: [
      {
        label: 'Users & Roles',
        to: paths.users,
        icon: Users,
        permission: 'manage:users',
      },
      {
        label: 'Billing',
        to: paths.billing,
        icon: CreditCard,
        permission: 'manage:billing',
      },
    ],
  },
  {
    label: 'Support',
    items: [
      {
        label: 'Help',
        to: paths.help,
        icon: CircleHelp,
        permission: 'view:overview',
      },
    ],
  },
]

/** Post-MVP nav entries, kept here so Phase F has an exact target. */
export const POST_MVP_NAV_ITEMS: NavItem[] = [
  {
    label: 'Live Activity',
    to: paths.activity,
    icon: Activity,
    permission: 'view:activity',
  },
  {
    label: 'Security & Audit',
    to: paths.security,
    icon: ShieldCheck,
    permission: 'view:security',
  },
]
