import '@testing-library/jest-dom/vitest'

import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  // Services persist the session in localStorage; leaking it across tests
  // would make auth-dependent cases order-sensitive.
  localStorage.clear()
})
