import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/features/auth/useAuth'
import { paths } from '@/routes/paths'
import { authService } from '@/services/authService'
import { toAppError } from '@/services/errors'

const schema = z.object({
  email: z.email('Enter a valid email address'),
})

type FormValues = z.infer<typeof schema>

/** USER_STORIES US-1.2 / PRD §7.2. States: default, processing, success, error. */
export function ForgotPasswordPage() {
  const { user } = useAuth()
  const [isSent, setIsSent] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  if (user) {
    return <Navigate to={paths.overview} replace />
  }

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      await authService.requestPasswordReset(values.email)
      setIsSent(true)
    } catch (error) {
      setFormError(toAppError(error).description)
    }
  })

  return (
    <div className="grid min-h-screen place-items-center bg-canvas p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <img src="/logo.svg" alt="" width={44} height={44} />
          <h1 className="mt-3 text-xl font-bold tracking-tight">Forgot password</h1>
          <p className="mt-1 text-sm text-ink-secondary">
            Enter your email and we will send reset instructions.
          </p>
        </div>

        {isSent ? (
          /*
           * Success replaces the form rather than annotating it. Leaving the
           * field in place would let someone submit address after address and
           * compare responses — exactly what the wording below prevents.
           */
          <div className="rounded-lg border border-border bg-surface p-6 text-center shadow-sm">
            <p className="text-sm font-semibold text-ink">Check your email</p>
            <p className="mt-2 text-sm text-ink-secondary">
              If an account exists for that address, reset instructions are on the way.
            </p>
            <Link
              to={paths.login}
              className="mt-4 block text-sm font-medium text-brand-ink hover:underline"
            >
              Back to sign in
            </Link>
          </div>
        ) : (
          <form
            onSubmit={onSubmit}
            noValidate
            className="rounded-lg border border-border bg-surface p-6 shadow-sm"
          >
            {formError ? (
              <p
                role="alert"
                className="mb-4 rounded-sm bg-danger-soft px-3 py-2 text-sm text-danger"
              >
                {formError}
              </p>
            ) : null}

            <Field label="Email" htmlFor="email" error={errors.email?.message}>
              <Input type="email" autoComplete="email" {...register('email')} />
            </Field>

            <Button type="submit" isLoading={isSubmitting} className="w-full">
              {isSubmitting ? 'Sending…' : 'Send reset link'}
            </Button>

            <Link
              to={paths.login}
              className="mt-3 block text-center text-sm font-medium text-brand-ink hover:underline"
            >
              Back to sign in
            </Link>
          </form>
        )}
      </div>
    </div>
  )
}
