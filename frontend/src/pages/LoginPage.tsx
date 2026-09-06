import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from '@/features/auth/useAuth'
import { paths } from '@/routes/paths'
import { toAppError } from '@/services/errors'

const schema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
})

type FormValues = z.infer<typeof schema>

/** USER_STORIES US-1.1. */
export function LoginPage() {
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
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
      await signIn(values.email, values.password)
      // Return the user to whatever they were trying to reach.
      const from = (location.state as { from?: Location } | null)?.from
      navigate(from?.pathname ?? paths.overview, { replace: true })
    } catch (error) {
      setFormError(toAppError(error).description)
    }
  })

  return (
    <div className="grid min-h-screen place-items-center bg-canvas p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <img src="/logo.svg" alt="" width={44} height={44} />
          <h1 className="mt-3 text-xl font-bold tracking-tight">
            GuideAnts <span className="text-brand">Concierge</span>
          </h1>
          <p className="mt-1 text-sm text-ink-secondary">Manage your AI Concierge</p>
        </div>

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

          <label htmlFor="email" className="mb-1.5 block text-sm font-semibold">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'email-error' : undefined}
            className="mb-1 w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm"
            {...register('email')}
          />
          {errors.email ? (
            <p id="email-error" className="mb-3 text-xs text-danger">
              {errors.email.message}
            </p>
          ) : (
            <div className="mb-3" />
          )}

          <label htmlFor="password" className="mb-1.5 block text-sm font-semibold">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'password-error' : undefined}
            className="mb-1 w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm"
            {...register('password')}
          />
          {errors.password ? (
            <p id="password-error" className="mb-3 text-xs text-danger">
              {errors.password.message}
            </p>
          ) : (
            <div className="mb-3" />
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-sm bg-brand px-4 py-2.5 text-sm font-semibold text-ink-inverse hover:bg-brand-strong disabled:opacity-60"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>

          <Link
            to={paths.forgotPassword}
            className="mt-3 block text-center text-sm font-medium text-brand-ink hover:underline"
          >
            Forgot password?
          </Link>
        </form>

        {/* US-1.1 allows SSO to ship as visibly future-ready but inert. */}
        <div className="mt-4 grid gap-2">
          {['Microsoft', 'Google', 'Enterprise SSO'].map((provider) => (
            <button
              key={provider}
              type="button"
              disabled
              title="Single sign-on is not enabled for this organization yet"
              className="w-full cursor-not-allowed rounded-sm border border-border bg-surface px-4 py-2 text-sm font-medium text-ink-muted"
            >
              Sign in with {provider}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
