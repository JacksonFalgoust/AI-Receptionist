import { z } from 'zod'

import type { Terminology } from '@/types'

export interface TerminologyFormValues {
  customer: string
  reservation: string
  location: string
  employee: string
}

export const terminologyFormSchema = z.object({
  customer: z.string().trim().min(1, 'Enter what you call a customer'),
  reservation: z.string().trim().min(1, 'Enter what you call a reservation'),
  location: z.string().trim().min(1, 'Enter what you call a location'),
  employee: z.string().trim().min(1, 'Enter what you call an employee'),
})

export function terminologyToFormValues(terminology: Terminology): TerminologyFormValues {
  return { ...terminology }
}

export function formValuesToTerminology(values: TerminologyFormValues): Terminology {
  return {
    customer: values.customer.trim(),
    reservation: values.reservation.trim(),
    location: values.location.trim(),
    employee: values.employee.trim(),
  }
}
