/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** `'false'` points services at the real API; anything else keeps mocks on. */
  readonly VITE_USE_MOCKS?: string
  /** Comma-separated service names to bring live while VITE_USE_MOCKS stays on. */
  readonly VITE_LIVE_SERVICES?: string
  /** Overrides the default `/api` prefix (which the dev server proxies). */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
