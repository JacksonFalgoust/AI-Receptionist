/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** `'false'` points services at the real API; anything else keeps mocks on. */
  readonly VITE_USE_MOCKS?: string
  /** Overrides the default `/api` prefix (which the dev server proxies). */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
