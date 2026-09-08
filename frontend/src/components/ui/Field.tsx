import { cloneElement, isValidElement } from 'react'
import type { ReactElement } from 'react'

export interface FieldProps {
  label: string
  description?: string
  error?: string
  htmlFor: string
  children: ReactElement
}

export function Field({ label, description, error, htmlFor, children }: FieldProps) {
  const descriptionId = description ? `${htmlFor}-description` : undefined
  const errorId = error ? `${htmlFor}-error` : undefined
  const describedBy = [descriptionId, errorId].filter(Boolean).join(' ') || undefined

  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id: htmlFor,
        'aria-describedby': describedBy,
        'aria-invalid': Boolean(error),
      })
    : children

  return (
    <div className="mb-4">
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-semibold text-ink">
        {label}
      </label>
      {control}
      {description ? (
        <p id={descriptionId} className="mt-1 text-xs text-ink-muted">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="mt-1 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  )
}
