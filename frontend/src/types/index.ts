/**
 * Barrel for the domain model described in PRD §42.
 *
 * Import from `@/types` rather than reaching into individual files, so models
 * can be reorganised without touching consumers.
 */

export * from './activity'
export * from './analytics'
export * from './billing'
export * from './common'
export * from './concierge'
export * from './conversation'
export * from './integration'
export * from './knowledge'
export * from './organization'
export * from './routing'
export * from './testConcierge'
export * from './user'
export * from './workflow'
