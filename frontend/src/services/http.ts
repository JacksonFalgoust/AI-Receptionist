import { API_BASE_URL, SESSION_STORAGE_KEY } from './config'
import { AppError } from './errors'

/**
 * Thin fetch wrapper shared by every HTTP service implementation. It attaches
 * the session token and converts transport/status failures into `AppError`, so
 * no service has to hand-roll error handling.
 */

function readToken(): string | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return null
    return (JSON.parse(raw) as { token?: string }).token ?? null
  } catch {
    // Corrupt or unavailable storage is equivalent to being signed out.
    return null
  }
}

function errorForStatus(status: number, body: unknown): AppError {
  const detail =
    typeof body === 'object' && body !== null && 'detail' in body
      ? String((body as { detail: unknown }).detail)
      : undefined

  if (status === 401) {
    return new AppError({
      kind: 'unauthorized',
      title: 'Your session has expired',
      description: 'Sign in again to continue managing your Concierge.',
      actions: [{ label: 'Sign in', href: '/login' }],
    })
  }

  if (status === 403) {
    return new AppError({
      kind: 'forbidden',
      title: 'You do not have access to this',
      description:
        'Your role does not permit this action. Ask an administrator if you need access.',
    })
  }

  if (status === 404) {
    return new AppError({
      kind: 'not_found',
      title: 'Not found',
      description: detail ?? 'That record no longer exists or was moved.',
    })
  }

  if (status === 422 || status === 400) {
    return new AppError({
      kind: 'validation',
      title: 'Check the highlighted fields',
      description: detail ?? 'Some of the information provided is not valid.',
    })
  }

  return new AppError({
    kind: 'server',
    title: 'Something went wrong on our side',
    description:
      detail ?? 'The request could not be completed. Try again in a moment.',
    actions: [{ label: 'Retry', retry: true }],
  })
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = readToken()

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new AppError({
      kind: 'network',
      title: 'Cannot reach GuideAnts Concierge',
      description:
        'Check your network connection and try again. If you are on a corporate network, a proxy may be blocking the request.',
      actions: [{ label: 'Retry', retry: true }],
    })
  }

  if (response.status === 204) {
    return undefined as T
  }

  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    throw errorForStatus(response.status, body)
  }

  return body as T
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(data ?? {}) }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(data ?? {}) }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(data ?? {}) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
