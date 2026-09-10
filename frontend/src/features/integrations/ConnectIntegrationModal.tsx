import { useEffect, useState } from 'react'

import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { integrationAction } from '@/lib/integrationActions'
import { ACCOUNT_LABEL_FIELD, integrationAuthFields } from '@/lib/integrationAuthFields'
import type { AuthField } from '@/lib/integrationAuthFields'
import type { AppError } from '@/services/errors'
import type { ConnectIntegrationInput } from '@/services/integrationService'
import type { Integration } from '@/types'

export interface ConnectIntegrationModalProps {
  integration: Integration
  isOpen: boolean
  onClose: () => void
  onSubmit: (input: ConnectIntegrationInput) => void
  isPending: boolean
  error: AppError | null
}

/**
 * US-9.1's Connect / Continue setup / Repair form. Deliberately owns no
 * mutation: `IntegrationCard` runs it and feeds `isPending`/`error` back, so
 * mutation state lives in exactly one place and this stays a pure form.
 *
 * PRD §17.3 / §47: a secret starts empty on every path — including Repair,
 * where the account is already known — and the values only ever live in the
 * state below, which is discarded when the dialog closes.
 */
export function ConnectIntegrationModal({
  integration,
  isOpen,
  onClose,
  onSubmit,
  isPending,
  error,
}: ConnectIntegrationModalProps) {
  const action = integrationAction(integration.status)
  const fields = integrationAuthFields(integration.category)
  const [values, setValues] = useState<Record<string, string>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  // Reopening always starts from a clean form: the account name is a label the
  // card already shows, so it is prefilled; nothing else is, secrets least of
  // all.
  useEffect(() => {
    if (!isOpen) return
    setValues({ [ACCOUNT_LABEL_FIELD.name]: integration.connectedAccount ?? '' })
    setFieldErrors({})
  }, [isOpen, integration.connectedAccount])

  if (!action) return null

  function setValue(name: string, value: string) {
    setValues((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => {
      if (!current[name]) return current
      const next = { ...current }
      delete next[name]
      return next
    })
  }

  function handleClose() {
    // A connection attempt in flight must land before the dialog can be
    // dismissed — a delayed success would otherwise toast a connection the
    // user believed they had called off.
    if (isPending) return
    onClose()
  }

  function handleSubmit() {
    const allFields: AuthField[] = [ACCOUNT_LABEL_FIELD, ...fields]
    const nextErrors: Record<string, string> = {}
    for (const field of allFields) {
      if (field.required && (values[field.name] ?? '').trim() === '') {
        nextErrors[field.name] = `${field.label} is required.`
      }
    }
    setFieldErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    const credentials = fields.reduce<Record<string, string>>((acc, field) => {
      const value = (values[field.name] ?? '').trim()
      // An optional field left blank is omitted rather than sent as an empty
      // string, so a backend can tell "not provided" from "cleared".
      if (value !== '') acc[field.name] = value
      return acc
    }, {})

    onSubmit({
      accountLabel: (values[ACCOUNT_LABEL_FIELD.name] ?? '').trim(),
      credentials: Object.keys(credentials).length > 0 ? credentials : undefined,
    })
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={`${action.label} — ${integration.name}`}
      actions={
        <>
          <Button variant="ghost" onClick={handleClose} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} isLoading={isPending}>
            {action.label}
          </Button>
        </>
      }
    >
      <p className="mb-3 text-sm text-ink-secondary">{action.intro}</p>

      {error ? (
        <Alert tone="danger" title={error.title} description={error.description} />
      ) : null}

      {[ACCOUNT_LABEL_FIELD, ...fields].map((field) => (
        <Field
          key={field.name}
          label={field.label}
          htmlFor={`connect-${field.name}`}
          error={fieldErrors[field.name]}
        >
          <Input
            type={field.type === 'secret' ? 'password' : 'text'}
            autoComplete="off"
            value={values[field.name] ?? ''}
            invalid={Boolean(fieldErrors[field.name])}
            onChange={(event) => setValue(field.name, event.target.value)}
          />
        </Field>
      ))}

      <p className="mt-3 text-xs text-ink-muted">
        Credentials are stored securely and are never shown again once saved.
      </p>
    </Modal>
  )
}
