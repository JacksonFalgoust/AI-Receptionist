import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import { presetBounds } from '@/lib/dateRange'
import type { ConversationListParams } from '@/services/conversationService'
import type { Channel, ConversationOutcome, DateRangePreset } from '@/types'

const CHANNELS: Channel[] = ['voice', 'sms', 'web', 'other']
const OUTCOMES: ConversationOutcome[] = [
  'completed',
  'escalated',
  'abandoned',
  'failed',
  'follow_up_required',
]
const PRESETS: DateRangePreset[] = ['today', '7d', '30d']

export type RangeChoice = DateRangePreset | 'any'

export interface ConversationFilterState {
  search: string
  channel?: Channel
  outcome?: ConversationOutcome
  escalated?: boolean
  range: RangeChoice
  intent?: string
  locationId?: string
  assignedEmployee?: string
  page: number
}

/** Anything not in the domain is treated as absent — a hand-edited URL must not throw. */
function oneOf<T extends string>(value: string | null, allowed: T[]): T | undefined {
  return allowed.includes(value as T) ? (value as T) : undefined
}

export function useConversationFilters() {
  const [params, setParams] = useSearchParams()

  const state = useMemo<ConversationFilterState>(() => {
    const page = Number(params.get('page'))
    const escalated = params.get('escalated')

    return {
      search: params.get('q') ?? '',
      channel: oneOf(params.get('channel'), CHANNELS),
      outcome: oneOf(params.get('outcome'), OUTCOMES),
      escalated: escalated === 'true' ? true : escalated === 'false' ? false : undefined,
      range: oneOf(params.get('range'), PRESETS) ?? 'any',
      // `||`, not `??`: an empty param (`?intent=`) must be treated the same
      // as an absent one, or it counts toward activeCount while showing no
      // chip and no visible value anywhere.
      intent: params.get('intent') || undefined,
      locationId: params.get('location') || undefined,
      assignedEmployee: params.get('employee') || undefined,
      page: Number.isInteger(page) && page > 0 ? page : 1,
    }
  }, [params])

  const activeCount = useMemo(() => {
    const { search, channel, outcome, escalated, range, intent, locationId, assignedEmployee } =
      state
    return [
      search !== '',
      channel !== undefined,
      outcome !== undefined,
      escalated !== undefined,
      range !== 'any',
      intent !== undefined,
      locationId !== undefined,
      assignedEmployee !== undefined,
    ].filter(Boolean).length
  }, [state])

  const listParams = useMemo<ConversationListParams>(() => {
    const bounds = state.range === 'any' ? {} : presetBounds(state.range)
    return {
      search: state.search || undefined,
      channel: state.channel,
      outcome: state.outcome,
      escalated: state.escalated,
      intent: state.intent,
      locationId: state.locationId,
      assignedEmployee: state.assignedEmployee,
      ...bounds,
      page: state.page,
    }
  }, [state])

  const write = useCallback(
    (next: ConversationFilterState) => {
      const search = new URLSearchParams()
      if (next.search) search.set('q', next.search)
      if (next.channel) search.set('channel', next.channel)
      if (next.outcome) search.set('outcome', next.outcome)
      if (next.escalated !== undefined) search.set('escalated', String(next.escalated))
      if (next.range !== 'any') search.set('range', next.range)
      if (next.intent) search.set('intent', next.intent)
      if (next.locationId) search.set('location', next.locationId)
      if (next.assignedEmployee) search.set('employee', next.assignedEmployee)
      if (next.page > 1) search.set('page', String(next.page))
      setParams(search, { replace: true })
    },
    [setParams],
  )

  // Any filter change returns to page 1 — a narrower filter would otherwise
  // strand the reader on a page that no longer exists.
  const setFilter = useCallback(
    (patch: Partial<ConversationFilterState>) => write({ ...state, ...patch, page: 1 }),
    [state, write],
  )

  const setPage = useCallback((page: number) => write({ ...state, page }), [state, write])

  const clear = useCallback(() => write({ search: '', range: 'any', page: 1 }), [write])

  return { state, params: listParams, activeCount, setFilter, setPage, clear }
}
