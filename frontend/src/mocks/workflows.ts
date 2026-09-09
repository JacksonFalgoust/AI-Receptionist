import type { Workflow, WorkflowStep } from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

const NOW = Date.now()
const DAY = 24 * 60 * 60 * 1000

function isoDaysAgo(days: number): string {
  return new Date(NOW - days * DAY).toISOString()
}

function step(
  id: string,
  name: string,
  type: WorkflowStep['type'],
  extra: Partial<WorkflowStep> = {},
): WorkflowStep {
  return { id, name, type, ...extra }
}

export const workflowSeed: Workflow[] = [
  {
    id: 'wf_booking',
    organizationId: MOCK_ORGANIZATION_ID,
    name: 'Book an appointment',
    description: 'Collects what the client needs, checks availability, and confirms the booking.',
    status: 'active',
    version: 7,
    executionCount: 1284,
    lastUpdatedAt: isoDaysAgo(2),
    steps: [
      step('wfs_b1', 'Ask what the client needs', 'ask_customer'),
      step('wfs_b2', 'Check the client record', 'look_up', { requiredIntegrationId: 'int_customer_records' }),
      step('wfs_b3', 'Offer available times', 'look_up', { requiredIntegrationId: 'int_scheduling', errorBehavior: 'Offer a callback instead' }),
      step('wfs_b4', 'Confirm the chosen time', 'confirm'),
      step('wfs_b5', 'Create the appointment', 'execute_action', { requiredIntegrationId: 'int_scheduling', errorBehavior: 'Escalate to a team member', escalationBehavior: 'Route to the scheduling queue' }),
      step('wfs_b6', 'Send a written confirmation', 'send_communication'),
      step('wfs_b7', 'End the conversation', 'end'),
    ],
  },
  {
    id: 'wf_reschedule',
    organizationId: MOCK_ORGANIZATION_ID,
    name: 'Reschedule an appointment',
    description: 'Finds the existing appointment and moves it to a new time.',
    status: 'active',
    version: 4,
    executionCount: 613,
    lastUpdatedAt: isoDaysAgo(9),
    steps: [
      step('wfs_r1', 'Confirm who is calling', 'validate'),
      step('wfs_r2', 'Find the existing appointment', 'look_up', { requiredIntegrationId: 'int_scheduling' }),
      step('wfs_r3', 'Offer alternative times', 'ask_customer'),
      step('wfs_r4', 'Move the appointment', 'execute_action', { requiredIntegrationId: 'int_scheduling' }),
      step('wfs_r5', 'End the conversation', 'end'),
    ],
  },
  {
    id: 'wf_payment',
    organizationId: MOCK_ORGANIZATION_ID,
    name: 'Send a payment link',
    description: 'Confirms the amount owed and sends a payment link by text or email.',
    status: 'active',
    version: 3,
    executionCount: 287,
    lastUpdatedAt: isoDaysAgo(15),
    steps: [
      step('wfs_p1', 'Confirm the outstanding amount', 'look_up', { requiredIntegrationId: 'int_payments' }),
      step('wfs_p2', 'Check the amount against the approval threshold', 'make_decision', { escalationBehavior: 'Escalate anything over $2,000' }),
      step('wfs_p3', 'Send the payment link', 'send_communication', { requiredIntegrationId: 'int_payments' }),
      step('wfs_p4', 'End the conversation', 'end'),
    ],
  },
  {
    id: 'wf_complaint',
    organizationId: MOCK_ORGANIZATION_ID,
    name: 'Handle a complaint',
    description: 'Captures the details of a complaint and routes it to the right team member.',
    status: 'active',
    version: 2,
    executionCount: 96,
    lastUpdatedAt: isoDaysAgo(21),
    steps: [
      step('wfs_c1', 'Ask what went wrong', 'ask_customer'),
      step('wfs_c2', 'Record the complaint', 'execute_action', { requiredIntegrationId: 'int_customer_records' }),
      step('wfs_c3', 'Escalate to a team member', 'escalate', { escalationBehavior: 'Route to the client care queue' }),
    ],
  },
  {
    id: 'wf_onboarding',
    organizationId: MOCK_ORGANIZATION_ID,
    name: 'New client intake',
    description: 'Collects the details needed to open a new client record.',
    status: 'draft',
    version: 1,
    executionCount: 0,
    lastUpdatedAt: isoDaysAgo(1),
    steps: [
      step('wfs_o1', 'Collect contact details', 'ask_customer'),
      step('wfs_o2', 'Check the details are complete', 'validate'),
      step('wfs_o3', 'Create the client record', 'execute_action', { requiredIntegrationId: 'int_customer_records' }),
    ],
  },
  {
    id: 'wf_survey',
    organizationId: MOCK_ORGANIZATION_ID,
    name: 'Post-appointment follow-up',
    description: 'Sends a short follow-up message after a completed appointment.',
    status: 'inactive',
    version: 2,
    executionCount: 412,
    lastUpdatedAt: isoDaysAgo(48),
    steps: [
      step('wfs_s1', 'Wait for the appointment to complete', 'validate'),
      step('wfs_s2', 'Send the follow-up message', 'send_communication'),
      step('wfs_s3', 'End the conversation', 'end'),
    ],
  },
]
