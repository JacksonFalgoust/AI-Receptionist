import type { Booking } from './booking'
import type { Id, IsoDateTime, PageRequest, Paginated } from './common'

export interface Customer {
  id: Id
  name: string | null
  email: string | null
  phone: string | null
  createdAt: IsoDateTime | null
  booqableUrl: string
  /** Null when the backend could not load bookings. */
  bookingCount: number | null
  lastBookingAt: IsoDateTime | null
}

export interface CustomerDetail {
  customer: Customer
  bookings: Booking[]
  fetchedAt: IsoDateTime
}

export interface CustomersPage extends Paginated<Customer> {
  fetchedAt: IsoDateTime
}

export interface CustomerListParams extends PageRequest {
  q?: string
  refresh?: boolean
}
