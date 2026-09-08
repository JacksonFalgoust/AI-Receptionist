/** Shared primitives used across every domain model. */

export type Id = string

/** ISO-8601 timestamp. Kept as a string so payloads survive JSON round-trips. */
export type IsoDateTime = string

/**
 * PRD §41: every customer-owned record belongs to an organization, and many
 * also belong to a location. Domain models spread this rather than redeclaring
 * the fields, so tenancy can never be forgotten on a new model.
 */
export interface TenantScoped {
  organizationId: Id
  locationId?: Id
}

/** PRD §46: conversation history and audit logs are paginated, never loaded whole. */
export interface Paginated<T> {
  items: T[]
  page: number
  pageSize: number
  total: number
}

export interface PageRequest {
  page?: number
  pageSize?: number
}
