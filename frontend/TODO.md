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
- [x] **Form primitives** (A1, US-0.2) — `Button`, `IconButton`, `Input`, `Textarea`, `Select`, `Checkbox`, `Radio`, `Toggle`, `Field`; `LoginPage` refactored onto them
- [x] **Layout & display primitives** (A2, US-0.2) — `Panel`/`PanelHeader`, `PageHeader`, `SectionHeader`, `StatusPill`, `Badge`, `Avatar`, `Alert`, `Breadcrumb`, `Tabs`
- [x] **Overlay primitives + providers** (A3, US-0.2, US-14.2) — `Modal`, `Drawer`, `Dropdown`, `Tooltip`, `Toast`/`ToastProvider`, `ConfirmDialog`/`useConfirm`; both providers mounted in `App.tsx`
- [x] **Data-display primitives** (A4, US-0.2) — `Table` (on `@tanstack/react-table` v9), `Pagination`, `SearchInput`, `FilterBar`, `EmptyState`, `Skeleton`, `KpiCard`, `Timeline`, `ActivityFeed`, `ChatBubble`
- [x] **Async-state boundary** (A5, US-0.3, PRD §39) — `QueryBoundary` + `ErrorState`; session expiry routes a 401 from any query or mutation back to `/login` with a message
- [x] **Service modules + mock data** (A6, US-0.3) — thirteen services (the eleven listed, plus `notificationService` and `organizationService`, both needed by A7) over a fixtures/store/query mock stack in `src/mocks/`; reads honour filters and pagination, writes mutate an in-memory store, no presentational component imports `src/mocks/` (PRD §38)
- [x] **Header panels** (A7, US-0.1, PRD §6.2) — organization selector, Concierge status panel, notification centre, user menu; `Topbar` is composition-only
- [x] **Forgot password** (A8, US-1.2) — default, processing, success, and error states; success copy does not reveal whether the account exists
- [x] **Overview KPI row** (B1, US-2.2) — the five KPIs `dashboardService.getOverview()` returns, label + value only; loading holds the five-card shape so nothing reflows when the numbers land
- [x] **Concierge Status card** (B2, US-2.3) — state, last configuration change, Voice/SMS health, connected systems, Test Concierge, and a confirmed Pause that toggles to Resume; shares the header badge's query key, so pausing updates both
- [x] **Recent Activity feed** (B3, US-2.4) — time, type, customer/context, channel, and outcome per item, each linking to its conversation; `ActivityStatus` joined `KnownStatus` so an activity outcome reads as itself rather than borrowing a workflow label. Introduces the two-column `dash-grid` pairing it with the B2 status card
- [x] **Recent Escalations** (B4, US-2.5) — Customer, Time, Reason, Assigned, Status across all four statuses, unassigned called out rather than left blank, each customer linking to the conversation that escalated. `Table` gained an optional `frame` so it sits flush inside a `Panel`
- [x] **Overview page assembly** (B5, US-2.1) — `DateScope` control (Today / 7 days / 30 days) in the page header, threaded into the KPI row and both feeds; no Export. `getRecentActivity`/`getRecentEscalations` now take a `DateRange`, and the activity/escalation seeds spread across a month so the control has visible effect
- [x] **Conversations list** (B6, US-3.1) — eight columns, five-field search, all seven filters (four visible, three behind a disclosure) and pagination, with filter state in the URL so a query can be bookmarked and shared. `Conversation` gained `escalationStatus`, `ConversationOutcome` joined `KnownStatus`, and the escalation seed was realigned onto conversations that actually escalated
- [x] **Conversation detail** (B7, US-3.2) — summary strip, AI summary in business language, transcript across all three speakers, and an action timeline whose system details expand behind a native disclosure. `Timeline` gained an optional `details` slot; a fixture test guards PRD §47 where it can actually be enforced
- [x] **Analytics** (B8, US-4.1) — the three allowed KPIs and the Top customer intents table, scoped by `DateScope` and defaulting to 30 days. `Kpi.format` was declared but never implemented, so a rate would have read "20" and a duration "303"; `formatKpi` now backs both this row and Overview's. No chart: US-4.1, the prototype and PRD §12.2 all stop short of requiring one
- [x] **Knowledge library** (C1, US-5.1) — the six PRD §16.2 columns, search, and type/status filters over the whole library, with filter state in the URL so "everything that needs review" is a shareable link. All six PRD §16.3 add actions ship under one trigger, five seeding the editor's type and "Add business information" leaving it open, since six actions cannot preselect ten types. Both filters list every domain value rather than the prototype's shortened set, which left six seeded types unreachable. The add and Edit links resolve to US-5.2's editor route, a stub until C2 — the same order B6 and B7 took. `EmptyState` gained an optional `href` so a CTA that navigates is a link; the seed grew to 34 items so pagination has a second page to reach
- [x] **Knowledge editor** (C2, US-5.2) — the seven PRD §16.4 fields plus one that only appears for the type that needs it: Website address for `url`, a file picker for `document`. Both add actions that needed a source `knowledgeService` had no field for now have one — `CreateKnowledgeInput` gained optional `status`/`source`. The Active toggle isn't a strict two-state switch: turning it on always sets Active, but turning it off preserves Processing/Needs review/Error rather than overwriting a status the system set, shown as a pill with an explanation above the toggle; a fresh document upload sets Processing regardless of the toggle, since nothing is editable until it's been read. Create and update both toast and return to the library rather than staying on the item, which sidesteps resyncing the form's defaults from a server response. Delete sits behind `useConfirm()`, edit-route only. A missing id needs no branch of its own — the service's existing `not_found` AppError and `QueryBoundary` already handle it
- [x] **Configuration — business profile** (C3, US-6.1) — name, description, phone, website, time zone, address, locations, and business hours, validated. `BusinessProfile` had no `locations` field yet; added as free text (e.g. "3 locations") rather than a per-location manager, matching the prototype and PRD §13.1 — a real multi-location editor is the Post-MVP multi-organization item, not this. Business hours got a real seven-row editor (day, Closed toggle, Open/Close time inputs) rather than the prototype's single text field, since `BusinessHours[]` already modeled per-day open/close. This section saves its own draft (`conciergeService.saveDraft({ businessProfile })`, toasted) rather than waiting on a page-level action — the page-level Save Draft / Publish pair, plus Identity, Terminology, and Preview, are C4's, which will fold this section under them
- [x] **Configuration — identity, terminology, publishing** (C4, US-6.1) — Identity (name, greeting, closing, voice, tone presets + a custom-tone description, primary language, supported languages), Terminology (built for real rather than stubbed: the four PRD §16.3 terms), and Preview join C3's Business profile under one `Tabs` shell, one shared `useForm`/`FormProvider`, and one Save Draft / Publish pair — `BusinessProfileForm` became `BusinessProfileFields`, reading `businessProfile.*` off the shared form instead of owning one. `Tabs` gained an optional `hasError` per item (a red dot) so an error on a tab the user isn't viewing is never invisible; failing validation on Save Draft/Publish now also toasts, since a shared form can fail from a tab that's out of sight with no other cue. Publish always saves the on-screen values before calling `publish()`, so what gets published can never be a stale draft from before the user's last edit; only Publish invalidates the header badge's status query, since only `publish()` touches `lastConfigurationChangeAt`. Preview reads the last-*saved* greeting/closing, not live keystrokes. Voice and Primary language are small curated selects (this app has no live TTS/locale catalog yet); both, plus Supported languages' checkboxes, guard against a saved value the curated list doesn't cover (`src/lib/selectOptions.ts`) rather than silently blanking or dropping it — the seed's `voice` needed updating to match once introduced, the same way `locations` did in C3

---

## Phase B — Operations

**Complete.** All eight tasks shipped; see the Done list above.

## Phase C — Concierge administration

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
