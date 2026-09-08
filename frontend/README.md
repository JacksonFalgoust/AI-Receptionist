# GuideAnts Concierge — Admin Frontend

React + TypeScript admin console for GuideAnts Concierge. Implements the
[Master Frontend PRD](../../GuideAntsConcierge/docs/GuideAnts_Concierge_Master_Frontend_PRD.md)
and [user stories](../../GuideAntsConcierge/docs/USER_STORIES.md), with the
static HTML prototype in that repo as the visual reference.

Remaining work and its order live in [TODO.md](./TODO.md).

## Commands

```bash
npm install        # install dependencies
npm run dev        # dev server on http://localhost:5173
npm run typecheck  # tsc, no emit
npm run lint       # oxlint
npm test           # vitest, single run
npm run test:watch # vitest, watch mode
npm run build      # typecheck + production build to dist/
```

## Signing in

The app ships with mock services, so any email works with the password
`concierge`. The **email local-part selects your role**, which is how
role-based navigation is exercised before a real identity provider exists:

| Email | Signs in as |
|---|---|
| `owner@horizonpartners.com` | Owner (full access) |
| `manager@horizonpartners.com` | Manager (no billing, users, or security) |
| `analyst@horizonpartners.com` | Analyst (analytics only) |
| `viewer@horizonpartners.com` | Viewer (read-only) |
| anything else | Owner |

## Architecture

```
src/
  styles/      theme.css — design tokens ported from the prototype
  types/       domain models (PRD §42)
  services/    one module per domain (PRD §37); each picks a mock or HTTP impl
  mocks/       sample data, imported only by services (PRD §38)
  components/ui/      design-system primitives (PRD §34)
  components/layout/  AppShell, Sidebar, Topbar
  features/    domain components grouped by area
  pages/       route-level screens
  routes/      route table, path constants, ProtectedRoute
  lib/         cn(), permissions, formatters
```

Two rules keep this from tangling:

1. **Presentational components never import from `mocks/`.** Data reaches them
   through a service. That is the seam that lets the FastAPI backend replace
   mocks without redesigning any UI.
2. **Every service failure becomes an `AppError`** carrying a human-readable
   title, description, and next actions — so error UI is structural rather than
   rewritten per screen (PRD §27).

## Connecting to the backend

Mocks are on by default. To point the same service interfaces at the FastAPI
app in `../app`:

```bash
cp .env.example .env.local   # then set VITE_USE_MOCKS=false
```

The dev server proxies `/api` to `http://localhost:8080`, so the browser stays
on one origin and no CORS configuration is needed. Note that the endpoints the
HTTP implementations call do not exist on the backend yet — see TODO.md.

## Access control

`src/lib/permissions.ts` maps the six PRD roles to capabilities, and
`ProtectedRoute` uses them to gate routes and nav items. This is navigation
convenience only: per PRD §40, the backend must enforce every one of these
rules independently before any real API ships.
