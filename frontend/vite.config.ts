/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * Pin the timezone so `Intl.DateTimeFormat` renders identically on a
 * developer's machine and in CI. Without it a date-only assertion such as
 * "Aug 30, 2026" passes in UTC and fails at UTC-5, where the same instant is
 * still Aug 29 — so date formatting could only ever be tested loosely.
 */
process.env.TZ = 'UTC'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // The FastAPI bridge runs on 8080. Proxying keeps the browser on one
    // origin, so switching VITE_USE_MOCKS=false needs no CORS setup.
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    restoreMocks: true,
    env: {
      // .env lists live-backed services in VITE_LIVE_SERVICES so the app
      // talks to the real API in dev/prod. isLive() (services/config.ts)
      // honors that list even when VITE_USE_MOCKS=true, so without this
      // override, tests for "live" services (auth, conversations, knowledge,
      // workflows, configuration) skip their mocks and call the real
      // backend with fetch('/api/...'). There is no backend in test runs, so
      // those calls fail -- and on CI the failed fetch hangs rather than
      // rejecting quickly, stalling the whole suite instead of failing it.
      // Tests must never depend on a live backend, so force every service
      // back to its mock here regardless of what .env lists.
      VITE_LIVE_SERVICES: '',
    },
  },
})
