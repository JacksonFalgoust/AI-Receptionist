import type { Id, IsoDateTime } from './common'

export interface Location {
  id: Id
  name: string
  address?: string
  timezone: string
}

export interface Organization {
  id: Id
  name: string
  /** PRD §41: a user may administer more than one organization. */
  locations: Location[]
  createdAt: IsoDateTime
}
