/**
 * Temporary stand-in for a screen that has not been built yet.
 *
 * Every route in PRD §35 resolves from day one, so navigation is never broken
 * while the app is under construction. Each page names the user story that
 * replaces it — see TODO.md. Delete this component once no page imports it.
 */
export function PlaceholderPage({
  eyebrow,
  title,
  description,
  story,
}: {
  eyebrow: string
  title: string
  description: string
  /** User story id from docs/USER_STORIES.md, e.g. "US-2.1". */
  story: string
}) {
  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-xs font-bold tracking-[0.08em] text-ink-muted uppercase">{eyebrow}</p>
      <h1 className="mt-1 text-2xl font-bold tracking-tight">{title}</h1>
      <p className="mt-1.5 max-w-2xl text-sm text-ink-secondary">{description}</p>

      <div className="mt-6 rounded-lg border border-dashed border-border-strong bg-surface p-10 text-center">
        <p className="text-sm font-semibold">This screen has not been built yet</p>
        <p className="mt-1 text-sm text-ink-secondary">
          Tracked as <span className="font-semibold text-brand-ink">{story}</span> in TODO.md.
        </p>
      </div>
    </div>
  )
}
