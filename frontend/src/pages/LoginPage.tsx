import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
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

          <Field label="Email" htmlFor="email" error={errors.email?.message}>
            <Input type="email" autoComplete="email" {...register('email')} />
          </Field>

          <Field label="Password" htmlFor="password" error={errors.password?.message}>
            <Input type="password" autoComplete="current-password" {...register('password')} />
          </Field>

          <Button type="submit" isLoading={isSubmitting} className="w-full">
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>

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
            <Button
              key={provider}
              type="button"
              variant="ghost"
              disabled
              title="Single sign-on is not enabled for this organization yet"
              className="w-full cursor-not-allowed"
            >
              Sign in with {provider}
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}
