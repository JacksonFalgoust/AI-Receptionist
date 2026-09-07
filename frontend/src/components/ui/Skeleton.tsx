export type SkeletonVariant = 'text' | 'card' | 'table'

export interface SkeletonProps {
  variant?: SkeletonVariant
  rows?: number
}

export function Skeleton({ variant = 'text', rows = 3 }: SkeletonProps) {
  return (
    <div role="status" aria-label="Loading" className="animate-pulse">
      {variant === 'text'
        ? Array.from({ length: rows }).map((_, index) => (
            <div key={index} data-skeleton-row className="mb-2 h-3 rounded bg-canvas-tint" />
          ))
        : null}
      {variant === 'card' ? <div className="h-32 rounded-lg bg-canvas-tint" /> : null}
      {variant === 'table' ? (
        <div className="space-y-2">
          {Array.from({ length: rows }).map((_, index) => (
            <div key={index} data-skeleton-row className="h-8 rounded bg-canvas-tint" />
          ))}
        </div>
      ) : null}
    </div>
  )
}
