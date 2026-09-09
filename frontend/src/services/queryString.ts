/**
 * Serialises service filter objects for HTTP implementations. Undefined values
 * are dropped so an absent filter never becomes the literal string
 * "undefined" in a query string.
 */
export function toQueryString(
  params: Record<string, string | number | boolean | undefined>,
): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value))
  }
  const serialised = search.toString()
  return serialised ? `?${serialised}` : ''
}
