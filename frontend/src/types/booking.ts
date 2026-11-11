import type { Id, IsoDateTime, PageRequest, Paginated } from './common'

export type BookingView = 'upcoming' | 'past'
export type BookingLabel = 'out_now' | 'overdue' | 'not_picked_up' | 'returned' | 'canceled'
export type PaymentLabel = 'paid' | 'unpaid' | 'partly_paid'

export interface BookingLineItem {
  name: string | null
  quantity: number | null
}

export interface Booking {
  id: Id
  number: number | null
  label: BookingLabel | null
  customerName: string | null
  customerPhone: string | null
  customerEmail: string | null
  items: BookingLineItem[] | null
  itemCount: number | null
  startsAt: IsoDateTime | null
  stopsAt: IsoDateTime | null
  totalCents: number
  payment: PaymentLabel
  booqableUrl: string
}

export interface BookingSummary {
  pickupsToday: number
  returnsToday: number
  next7Days: number
  unpaid: number
}

export interface BookingsPage extends Paginated<Booking> {
  summary: BookingSummary
  fetchedAt: IsoDateTime
}

export interface BookingListParams extends PageRequest {
  view?: BookingView
  refresh?: boolean
}
