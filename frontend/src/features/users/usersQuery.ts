/**
 * Shared by `UsersPage`, which reads the list, and by both modals, which
 * invalidate it after a mutation. A module of its own rather than co-located
 * with a component (the way `ROUTING_RULES_KEY` lives in `RuleStatusToggle`)
 * because three files need it and none of them owns it.
 */
export const USERS_KEY = ['users'] as const
