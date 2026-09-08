// src/components/ui/Field.test.tsx
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { Field } from './Field'
import { Input } from './Input'

describe('Field', () => {
  it('associates the label with the control via htmlFor/id, with no aria-describedby when neither description nor error is set', () => {
    render(
      <Field label="Email" htmlFor="email">
        <Input />
      </Field>,
    )
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).not.toHaveAttribute('aria-describedby')
  })

  it('wires the description into aria-describedby when there is no error', () => {
    render(
      <Field label="Email" htmlFor="email" description="We only use this to sign you in.">
        <Input />
      </Field>,
    )
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-describedby', 'email-description')
    expect(input).not.toHaveAttribute('aria-invalid', 'true')
  })

  it('wires the error into aria-describedby and sets aria-invalid, rendering it as an alert', () => {
    render(
      <Field label="Email" htmlFor="email" error="Enter a valid email address">
        <Input />
      </Field>,
    )
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-describedby', 'email-error')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email address')
  })

  it('describes by both description and error when both are present', () => {
    render(
      <Field label="Email" htmlFor="email" description="Hint" error="Required">
        <Input />
      </Field>,
    )
    expect(screen.getByLabelText('Email')).toHaveAttribute(
      'aria-describedby',
      'email-description email-error',
    )
  })
})
