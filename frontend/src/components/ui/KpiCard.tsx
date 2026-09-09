export interface KpiCardProps {
  label: string
  value: string | number
}

/** US-2.2: label and primary metric only — no trend, no comparison text. */
export function KpiCard({ label, value }: KpiCardProps) {
  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-ink">{value}</p>
    </article>
  )
}
