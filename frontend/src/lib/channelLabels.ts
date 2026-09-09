import type { Channel } from '@/types'

/**
 * Business-language name for each channel, shared by every surface that shows
 * one — the header status panel, the Overview status card, and the Recent
 * Activity feed. Kept here so the three can never disagree.
 */
export const CHANNEL_LABELS: Record<Channel, string> = {
  voice: 'Voice',
  sms: 'SMS',
  web: 'Web',
  other: 'Other',
}
