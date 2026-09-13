/**
 * Money for the billing screen. Amounts are stored in cents so no float ever
 * represents a price; the currency code comes from the record rather than the
 * locale, so a non-USD invoice still formats as its own currency.
 *
 * Locale is pinned to en-US for the same reason `formatDate` and `formatKpi`
 * pin theirs: deterministic in tests, identical across users until the product
 * supports localised formats.
 */
export function formatMoney(amountCents: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amountCents / 100)
}
