import type { Id, IsoDateTime } from './common'
import type { Channel } from './conversation'

/** A single headline number. USER_STORIES US-2.2: label + value only, no trend. */
export interface Kpi {
  id: string
  label: string
  value: number
  /** Renders 4:12 for durations, 12% for rates, plain integers otherwise. */
  format?: 'number' | 'percent' | 'duration'
}

export interface OverviewSummary {
  kpis: Kpi[]
}

export interface IntentVolume {
  intent: string
  volume: number
}

export interface TimeSeriesPoint {
  at: IsoDateTime
  value: number
  channel?: Channel
}

export interface AnalyticsSummary {
  kpis: Kpi[]
  topIntents: IntentVolume[]
  volumeOverTime: TimeSeriesPoint[]
  channelDistribution: { channel: Channel; count: number }[]
}

export type DateRangePreset = 'today' | '7d' | '30d' | 'custom'

export interface DateRange {
  preset: DateRangePreset
  from?: IsoDateTime
  to?: IsoDateTime
}

/** PRD §8.6 — deferred past the MVP, modelled now so the tail phase has a target. */
export type InsightKind =
  | 'opportunity'
  | 'warning'
  | 'trend'
  | 'recommendation'
  | 'operational'

export interface Insight {
  id: Id
  kind: InsightKind
  title: string
  body: string
}
