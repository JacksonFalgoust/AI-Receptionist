/**
 * Every route in the application, from PRD §35. Centralised so links are typed
 * and a path change never leaves a dead `<Link>` behind (PRD §52: no broken
 * navigation).
 */
export const paths = {
  login: '/login',
  forgotPassword: '/forgot-password',
  invite: (token = ':token') => `/invite/${token}`,

  overview: '/overview',
  conversations: '/conversations',
  conversation: (id = ':id') => `/conversations/${id}`,
  activity: '/activity',
  analytics: '/analytics',

  knowledge: '/concierge/knowledge',
  configuration: '/concierge/configuration',
  features: '/concierge/features',
  workflows: '/concierge/workflows',
  workflow: (id = ':id') => `/concierge/workflows/${id}`,

  integrations: '/integrations',
  routing: '/routing',

  users: '/admin/users',
  security: '/admin/security',
  billing: '/admin/billing',

  test: '/test',
  help: '/help',
} as const
