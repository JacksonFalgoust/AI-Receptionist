# GuideAnts Concierge Frontend — Build Order

Ordered backlog for the React admin console. Sequenced by the USER_STORIES
sprint slices (A–E), which are already dependency-ordered, with PRD-only
requirements that the MVP explicitly cuts collected in **Phase F**.

Sources:
- [Master Frontend PRD](../../GuideAntsConcierge/docs/GuideAnts_Concierge_Master_Frontend_PRD.md) — `PRD §n` references below
- [User stories](../../GuideAntsConcierge/docs/USER_STORIES.md) — `US-n.n` references below
- Static HTML prototype in the `GuideAntsConcierge` repo — the visual reference for every screen

**Work top to bottom.** Phase A is a hard prerequisite: nearly every later task
consumes its primitives and services. Within a phase, tasks are ordered so each
one only depends on things above it.

---

## Done

- [x] **Project scaffold** — Vite + React + TypeScript, path alias `@/*`, Vitest + Testing Library, oxlint
- [x] **Design tokens** — prototype `:root` palette ported to Tailwind v4 `@theme` in `src/styles/theme.css`
- [x] **Domain model** — PRD §42 interfaces in `src/types/`, all tenancy-scoped
- [x] **Service seam** — `AppError` normalisation, `http` client, `USE_MOCKS` switch (`src/services/`)
- [x] **Auth** — `AuthProvider`, `authService` with mock + HTTP implementations, session persistence
- [x] **Permissions** — six PRD roles mapped to capabilities (`src/lib/permissions.ts`)
- [x] **Routing** — every route in PRD §35 resolves; `ProtectedRoute` guards auth and role
- [x] **App shell** — sidebar (grouped nav, mobile drawer, Escape-to-close) + header
- [x] **Login** (US-1.1) — validation, human-readable errors, inert SSO placeholders
- [x] **CI** — frontend typecheck/lint/test/build job added to `.github/workflows/tests.yml`

---

## Phase A — Foundation

Everything here is shared infrastructure. Building screens before it means
duplicating markup that has to be torn out later (PRD §53.4).

### A1. Form primitives (US-0.2)
`src/components/ui/` — `Button`, `IconButton`, `Input`, `Textarea`, `Select`,
`Checkbox`, `Radio`, `Toggle`, and a `Field` wrapper handling label,
description, error text, and `aria-describedby` wiring.
- Every control takes a required accessible name; icon-only variants require `aria-label` (PRD §52).
- Button variants: primary, ghost, danger. Sizes: sm, md.
- Extract the styles currently inlined in `LoginPage.tsx` and refactor that page onto them.

### A2. Layout & display primitives (US-0.2)
`Panel` (+ `PanelHeader`), `PageHeader`, `SectionHeader`, `StatusPill`,
`Badge`, `Avatar`, `Alert`, `Breadcrumb`, `Tabs`.
- `StatusPill` must render a text label, never colour alone (PRD §31).
- One pill component serves every status union in `src/types/` — map status → tone in one place.

### A3. Overlay primitives + providers (US-0.2, US-14.2)
`Modal`, `Drawer`, `Dropdown`, `Tooltip`, `Toast` + `ToastProvider`,
`ConfirmDialog` + a `useConfirm()` hook.
- Focus trap, Escape to close, focus restored to the trigger on close.
- `useConfirm()` is what every destructive action calls (PRD §28) — build it once here.
- Mount `ToastProvider` in `App.tsx`.

### A4. Data-display primitives (US-0.2)
`Table` (sortable headers, sticky head, horizontal scroll container),
`Pagination`, `SearchInput`, `FilterBar`, `EmptyState`, `Skeleton`
(text/card/table variants), `KpiCard`, `Timeline`, `ActivityFeed`, `ChatBubble`.
- `Table` must stay generic over row type; no per-screen table copies.

### A5. Async-state boundary (US-0.3, PRD §39)
A `QueryBoundary` component (or hook) that renders Loading → Empty → Error →
Success from a TanStack Query result, using A4's `Skeleton`/`EmptyState` and an
`ErrorState` built from `AppError.title`/`.description`/`.actions`.
- Handles the `unauthorized` kind by redirecting to `/login` with a session-expired message (US-0.4).
- Every data view in Phases B–E goes through this. Nothing hand-rolls loading markup.

### A6. Service modules + mock data (US-0.3)
One module per domain in `src/services/`, each following the `authService`
pattern (interface → mock impl → HTTP impl → `USE_MOCKS` export):
`dashboardService`, `conversationService`, `analyticsService`,
`conciergeService`, `featureService`, `workflowService`, `knowledgeService`,
`integrationService`, `routingService`, `userService`, `billingService`.
- Realistic Horizon Partners sample data in `src/mocks/`, industry-neutral (PRD §53.9).
- Mock reads honour filters/pagination so list UIs are exercised properly.
- Mock writes mutate an in-memory store, so save/publish round-trips visibly work.
- **No presentational component imports from `src/mocks/`** (PRD §38).

### A7. Header panels (US-0.1, PRD §6.2)
Wire the four header controls that currently render but do nothing:
organization selector, Concierge status panel (state, channels, recent issues,
last configuration change), notification center, user menu (profile, settings,
logout).
- Logout calls `useAuth().signOut()` and returns to `/login`.
- Notification list comes from a service, not hard-coded.

### A8. Forgot password (US-1.2)
Replace the `ForgotPasswordPage` placeholder.
- States: default, processing, success, error. Success copy must not reveal whether the account exists.
- Link back to sign in.

---

## Phase B — Operations

### B1. Overview KPI row (US-2.2)
Exactly five: Conversations Today, Calls Answered, Requests Completed, Human
Escalations, Transactions Created. **Label + value only** — no sparkline, no
"vs yesterday". Loading and error states for the row.

### B2. Concierge Status card (US-2.3)
State + last configuration change, channels **Voice and SMS only** (no Web),
connected-systems summary with health indicators. Actions: Test Concierge,
Pause Concierge (via `useConfirm()`), link to Configuration.

### B3. Recent Activity feed (US-2.4)
Time, activity type, customer/context, channel, status per item. Links through
to Conversations. Empty state.

### B4. Recent Escalations (US-2.5)
Columns: Customer, Time, Reason, Assigned, Status (New / Assigned / In Progress
/ Resolved). Links to Escalation & Routing. Empty state.

### B5. Overview page assembly (US-2.1)
Compose B1–B4 into `/overview` with a date-scope control. **No Export button.**

### B6. Conversations list (US-3.1)
Columns: Date/Time, Customer, Channel, Intent, Outcome, Duration, Escalated,
Status. Search by name, phone, conversation ID, intent, keyword. Filters: date
range, channel, intent, outcome, escalated, location, assigned employee.
Pagination. Empty/loading/error states.

### B7. Conversation detail (US-3.2)
Summary block, AI summary in business language, transcript with
Customer/Concierge/Employee speakers, action timeline (action, system,
timestamp, result, success/error), expandable system details that never expose
credentials (PRD §10.5, §47). Breadcrumb back to Conversations.

### B8. Analytics (US-4.1)
KPI widgets: Total conversations, Escalation rate, Avg duration — **no
conversion rate**. Top customer intents table: Intent, Volume — **no trend
column**. Loading/empty/error. Lazy-load the charts (PRD §46).

---

## Phase C — Concierge administration

### C1. Knowledge library (US-5.1)
Table: Name, Type, Status, Source, Updated, Actions. Statuses: Active,
Processing, Needs Review, Error, Disabled. Search + type/status filters. Add
actions (Create FAQ, Add text, Upload document, Add URL, Create policy, Add
business information) — a subset may ship with a clear CTA for the rest. Empty
state: "Give Concierge something to work with".

### C2. Knowledge editor (US-5.2)
Fields: Title, Category, Content, Tags, Active/inactive, Effective date,
Expiration date. Validation on required fields. Save toast. Delete behind
`useConfirm()`.

### C3. Configuration — business profile (US-6.1)
Name, description, phone, website, timezone, address, locations, business
hours. Validation.

### C4. Configuration — identity, terminology, publishing (US-6.1)
Concierge name, greeting, closing, voice, tone presets (Professional, Friendly,
Casual, Formal, Custom), language(s). Terminology section (may be stubbed).
**Save Draft and Publish Changes as separate explicit actions** — saving must
never publish to production (PRD §13.4). Preview Greeting / Test Concierge
entry points. Publish confirmation.

### C5. Features (US-7.1)
Cards with name, description, status, required integration, config status, and
an enable toggle. Statuses: Enabled, Disabled, Setup Required, Connection
Required, Error. Toggling something needing setup routes to setup or shows the
next step. Confirm when disabling high-impact features (Payments, Answer
Calls) — the `highImpact` flag is already on the `Feature` type.

### C6. Workflow list (US-8.1)
Columns: Name, Description, Status, Version, Executions, Updated. Create CTA.
Empty state: "Create your first workflow".

### C7. Workflow detail + step editor (US-8.2)
Visual step list (drag-and-drop **not** required for MVP). All nine step types
from `WORKFLOW_STEP_TYPES`. Step editor: name, type, configuration, required
integration, error behavior, escalation behavior. Save Draft / Publish with
confirmation.
- Keep step rendering and step editing as separate components so Phase F's
  visual builder can reuse them (PRD §15.4).

---

## Phase D — Connect

### D1. Integrations catalog (US-9.1)
Cards: name, category, status, last activity, connected account, features using
the connection. Statuses: Connected, Not Connected, Setup Required, Connection
Error, Authentication Expired. Grouped or filterable by category. Empty state:
"Connect your first business system".

### D2. Integration connect / repair / disconnect (US-9.1)
Connect and Continue-setup flows, Repair for error and expired-auth states.
Disconnect behind `useConfirm()`. **Never display a secret after it is stored**
(PRD §17.3, §47).

### D3. Routing rules table (US-10.1)
Columns: Rule, Condition, Destination, Schedule, Priority, Status. Enable/
disable inline. Optional summary stats (active rules, escalations today).

### D4. Routing rule editor (US-10.1)
All conditions in `EscalationCondition`, all destinations in
`RoutingDestinationType`, schedules covering open hours / after hours /
weekends / holidays. Add, edit, delete with confirmation.

---

## Phase E — Administration & polish

### E1. Users & Roles (US-11.1)
Table: Name, Email, Role, Status, Last login. All six roles. Actions: Invite,
Edit role, Disable, Remove, Resend invitation. Disable/Remove confirmed. Invite
success toast; pending invites visibly distinct.

### E2. Billing (US-12.1)
Current plan, billing status, period, payment-method summary, usage metrics
(voice minutes, conversations, SMS, workflow executions). Invoices may be
stubbed. Placeholder data is acceptable.

### E3. Test Concierge drawer (US-13.1)
Global right-side drawer opened from the header, replacing the current link to
`/test`. Clearly labelled **TEST MODE**. Text simulation: send a message, see
the reply. Show actions executed / workflow / knowledge / integrations used
(may be mocked). Escape closes. Test traffic must not create production
transactions.
- Keep `/test` as a route rendering the same panel, so the PRD §22 route stays valid.

### E4. Help (US-14.1)
Search stub, getting started, links to Configuration and Integrations, contact
support CTA.

### E5. Cross-cutting quality pass (US-14.2)
- Every primary page has intentional empty + loading states.
- Toasts on every save/publish/invite/connect; error toasts state a next step.
- Confirmation on every destructive action listed in PRD §28.
- Responsive check: Overview, Conversations, and escalations usable on mobile.
- Accessibility sweep against WCAG 2.1 AA — labels, focus order, contrast, status never by colour alone.
- No console errors during normal interaction (PRD §52).

### E6. Backend integration
Replace mock implementations with live calls behind `VITE_USE_MOCKS=false`.
- Define the API contract against the FastAPI app in `../app`; the HTTP impls
  currently assume endpoints that do not exist yet.
- Conversation history is the natural first real feed — Conversation Relay
  calls already flow through `app/main.py`.
- **Enforce every permission in `src/lib/permissions.ts` server-side** (PRD §40).

---

## Phase F — Post-MVP (PRD requirements cut from the MVP)

Explicitly out of scope in USER_STORIES, captured here so nothing is lost. Not
ordered — pick by need.

- [ ] **Live Activity page** (PRD §11) — route and placeholder exist; add to `NAV_GROUPS` from `POST_MVP_NAV_ITEMS` in `src/components/layout/nav.ts`
- [ ] **Security & Audit page** (PRD §20) — same; `AuditEvent` type already defined
- [ ] **Concierge Insights on Overview** (PRD §8.6) — `Insight` type already defined
- [ ] **Conversation Volume chart on Overview** (PRD §8.4) — Today / 7d / 30d / custom, split by channel
- [ ] **Conversion rate + trend indicators** on Overview KPIs and Analytics (PRD §8.1)
- [ ] **Export** on Overview and Conversations
- [ ] **Web channel** on the Concierge Status card (PRD §8.2)
- [ ] **Onboarding wizard** (PRD §24) — 9 steps; the sidebar setup chip is currently static and should read real progress
- [ ] **Invitation acceptance** (PRD §7.3) — `/invite/:token` route and placeholder exist
- [ ] **Sidebar collapse to icon mode** (PRD §6.1) — `--sidebar-w-collapsed` token already defined
- [ ] **Voice playback** on conversation detail (PRD §10.3) — audio, speed, timestamp sync
- [ ] **Multi-organization switching** (PRD §41) — selector renders; needs real org list and tenant switching
- [ ] **Drag-and-drop workflow builder** (PRD §15.4)
- [ ] **Developer integrations** (PRD §17.3) — APIs, MCP servers, webhooks, custom tools
- [ ] **Custom roles** beyond the six defaults (PRD §19.2)
- [ ] **Table virtualization** for very large conversation and audit lists (PRD §46)

---

## Definition of done (every task)

From PRD §52 and the USER_STORIES definition of done:

- `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build` all pass
- No unresolved imports, no broken navigation, no console errors
- Loading, empty, success, and error states handled for every data view
- Forms validated; destructive actions confirmed; success and failure both visible
- Mock data reached through a service, never inlined in a presentational component
- Reusable primitives used rather than duplicated markup
- Mobile layout usable for the story's primary flow
- Route permissions respected
- No lorem ipsum; industry-neutral sample data
- Business language in UI copy — Knowledge, Workflows, Features; never tokens, embeddings, or prompts (PRD §3.1)
