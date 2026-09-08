import { cn } from '@/lib/cn'

export interface AvatarProps {
  name: string
  imageUrl?: string
  size?: 'sm' | 'md'
}

const SIZE_CLASSES: Record<'sm' | 'md', string> = {
  sm: 'h-6 w-6 text-[10px]',
  md: 'h-9 w-9 text-xs',
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return ''
  const first = parts[0][0]
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ''
  return (first + last).toUpperCase()
}

export function Avatar({ name, imageUrl, size = 'md' }: AvatarProps) {
  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={name}
        className={cn('rounded-full object-cover', SIZE_CLASSES[size])}
      />
    )
  }

  return (
    <div
      role="img"
      aria-label={name}
      className={cn(
        'flex items-center justify-center rounded-full bg-brand-soft font-semibold text-brand-ink',
        SIZE_CLASSES[size],
      )}
    >
      {initialsFor(name)}
    </div>
  )
}
