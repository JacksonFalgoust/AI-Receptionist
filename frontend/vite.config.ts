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
  },
})
