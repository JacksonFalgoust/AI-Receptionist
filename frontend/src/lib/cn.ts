import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge conditional class names, with later Tailwind utilities winning over
 * earlier conflicting ones. Lets a caller override a component's defaults via
 * `className` without needing `!important`.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
