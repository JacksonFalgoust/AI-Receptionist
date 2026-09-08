import type { KnowledgeItem, KnowledgeStatus, KnowledgeType } from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

const NOW = Date.now()
const DAY = 24 * 60 * 60 * 1000

function isoDaysAgo(days: number): string {
  return new Date(NOW - days * DAY).toISOString()
}

interface KnowledgeSeedInput {
  title: string
  type: KnowledgeType
  status: KnowledgeStatus
  source: string
  category: string
  tags: string[]
  content: string
}

const ENTRIES: KnowledgeSeedInput[] = [
  { title: 'What are your opening hours?', type: 'faq', status: 'active', source: 'Manual entry', category: 'General', tags: ['hours'], content: 'We are open Monday to Thursday 8:30am–5:30pm and Friday 8:30am–4:00pm, closed weekends.' },
  { title: 'Where are your offices?', type: 'faq', status: 'active', source: 'Manual entry', category: 'General', tags: ['locations'], content: 'We have two offices: 1200 Meridian Way, Suite 400, and 55 Riverside Plaza.' },
  { title: 'How do I reschedule an appointment?', type: 'faq', status: 'active', source: 'Manual entry', category: 'Appointments', tags: ['appointments', 'reschedule'], content: 'Call or text us at least 24 hours ahead and we will move your appointment to the next available time.' },
  { title: 'Do you offer evening appointments?', type: 'faq', status: 'active', source: 'Manual entry', category: 'Appointments', tags: ['appointments', 'hours'], content: 'Evening appointments are available on Tuesdays until 7:00pm by prior arrangement.' },
  { title: 'What payment methods do you accept?', type: 'faq', status: 'active', source: 'Manual entry', category: 'Billing', tags: ['billing', 'payments'], content: 'We accept all major cards and bank transfer. Payment links are sent by text or email.' },
  { title: 'Cancellation policy', type: 'policy', status: 'active', source: 'Manual entry', category: 'Policies', tags: ['policy', 'cancellation'], content: 'Appointments cancelled with less than 24 hours notice may be charged at 50% of the appointment fee.' },
  { title: 'Refund policy', type: 'policy', status: 'active', source: 'Manual entry', category: 'Policies', tags: ['policy', 'refunds'], content: 'Refund requests are reviewed within five business days. Any refund over $2,000 requires a manager approval.' },
  { title: 'Privacy commitment', type: 'policy', status: 'needs_review', source: 'Manual entry', category: 'Policies', tags: ['policy', 'privacy'], content: 'Client information is used only to deliver the services requested and is never sold.' },
  { title: 'Late arrival policy', type: 'policy', status: 'disabled', source: 'Manual entry', category: 'Policies', tags: ['policy'], content: 'Clients arriving more than 15 minutes late may need to rebook.' },
  { title: 'New client intake procedure', type: 'procedure', status: 'active', source: 'Manual entry', category: 'Operations', tags: ['intake'], content: 'Collect contact details, confirm the service required, and create the client record before booking.' },
  { title: 'Escalation procedure', type: 'procedure', status: 'active', source: 'Manual entry', category: 'Operations', tags: ['escalation'], content: 'Any complaint, refund request, or explicit request for a person goes to the client care queue.' },
  { title: 'Consultation service overview', type: 'service', status: 'active', source: 'Manual entry', category: 'Services', tags: ['services'], content: 'A 60-minute consultation covering objectives, current position, and recommended next steps.' },
  { title: 'Ongoing advisory service', type: 'service', status: 'active', source: 'Manual entry', category: 'Services', tags: ['services'], content: 'A monthly advisory retainer including a scheduled review and unlimited email support.' },
  { title: 'Document review service', type: 'service', status: 'processing', source: 'services-2026.docx', category: 'Services', tags: ['services'], content: 'Fixed-fee review of supplied documents with written feedback within five business days.' },
  { title: 'Standard service rates', type: 'pricing', status: 'active', source: 'Manual entry', category: 'Pricing', tags: ['pricing'], content: 'Consultation $180. Advisory retainer $650 per month. Document review from $240.' },
  { title: 'Package pricing', type: 'pricing', status: 'needs_review', source: 'Manual entry', category: 'Pricing', tags: ['pricing'], content: 'A three-consultation package is $480, saving $60 against the single-session rate.' },
  { title: 'North Office details', type: 'location', status: 'active', source: 'Manual entry', category: 'Locations', tags: ['locations'], content: '1200 Meridian Way, Suite 400. Parking is available in the adjoining garage.' },
  { title: 'Riverside Office details', type: 'location', status: 'active', source: 'Manual entry', category: 'Locations', tags: ['locations'], content: '55 Riverside Plaza. Street parking only; the building entrance is on the plaza side.' },
  { title: 'Company overview', type: 'product', status: 'active', source: 'Manual entry', category: 'General', tags: ['about'], content: 'Horizon Partners is a professional services firm supporting clients with planning and ongoing advice.' },
  { title: 'How Concierge should greet returning clients', type: 'instruction', status: 'active', source: 'Manual entry', category: 'Operations', tags: ['tone'], content: 'Acknowledge a returning client by name and reference their most recent appointment.' },
  { title: 'Handling questions we cannot answer', type: 'instruction', status: 'active', source: 'Manual entry', category: 'Operations', tags: ['escalation'], content: 'Say plainly that a team member will follow up, take a callback number, and escalate.' },
  { title: 'Client handbook 2026', type: 'document', status: 'active', source: 'client-handbook-2026.pdf', category: 'General', tags: ['handbook'], content: 'The full client handbook covering services, policies, and contact routes.' },
  { title: 'Service terms', type: 'document', status: 'error', source: 'service-terms.pdf', category: 'Policies', tags: ['policy'], content: 'The uploaded document could not be read. Re-upload it as a text-based PDF.' },
  { title: 'Public services page', type: 'url', status: 'active', source: 'https://horizonpartners.example.com/services', category: 'Services', tags: ['services', 'website'], content: 'Mirrors the public services listing so Concierge and the website never disagree.' },
]

export const knowledgeSeed: KnowledgeItem[] = ENTRIES.map((entry, index) => ({
  id: `kn_${String(index + 1).padStart(4, '0')}`,
  organizationId: MOCK_ORGANIZATION_ID,
  title: entry.title,
  type: entry.type,
  status: entry.status,
  source: entry.source,
  category: entry.category,
  content: entry.content,
  tags: entry.tags,
  updatedAt: isoDaysAgo(index + 1),
  effectiveDate: index % 4 === 0 ? isoDaysAgo(120) : undefined,
  expirationDate: index % 9 === 0 ? isoDaysAgo(-180) : undefined,
}))
