import type { Organization } from '@/types'

import { MOCK_ORGANIZATION_ID, MOCK_ORGANIZATION_NAME } from './session'

/**
 * One organization today. `organizationService` returns this list so the header
 * selector is real plumbing over a list of length one — Phase F's
 * multi-organization support swaps the data and nothing else.
 */
export const organizationSeed: Organization[] = [
  {
    id: MOCK_ORGANIZATION_ID,
    name: MOCK_ORGANIZATION_NAME,
    createdAt: '2024-03-11T09:00:00.000Z',
    locations: [
      {
        id: 'loc_north',
        name: 'North Office',
        address: '1200 Meridian Way, Suite 400',
        timezone: 'America/Chicago',
      },
      {
        id: 'loc_riverside',
        name: 'Riverside Office',
        address: '55 Riverside Plaza',
        timezone: 'America/Chicago',
      },
    ],
  },
]
