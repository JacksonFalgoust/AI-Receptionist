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
- [x] **Features** (C5, US-7.1) — cards for all nine PRD §14.1 features: name, description, `StatusPill`, required integration, and an enable `Toggle`. Nothing new needed in the domain layer — `Feature`/`FeatureStatus`, the nine-item seed covering all five statuses, and `featureService.setEnabled`'s validation-vs-not_found split already existed from A6. Each `FeatureCard` is self-contained like `ConciergeStatusCard`: its own mutation, confirming (`useConfirm()`) only before disabling a `highImpact` feature, and patching the shared `['features']` query cache on success rather than the page tracking which card is mid-action. Turning on something setup/connection-blocked shows the service's own `AppError` inline as an inbound next step (title, description, and its `View integration` action wired to actually navigate to `/integrations`) rather than a toast, since our toasts carry no actions to click
- [x] **Workflow list** (C6, US-8.1) — the six PRD §15.1 columns over `workflowService.list()`'s six-item seed, in a plain `Table`/`Panel` with no filters or pagination: neither the PRD nor the prototype's `workflows.html` calls for either here, unlike Knowledge (C1) or Conversations (B6). Nothing new needed in the domain or service layer — `Workflow`, its six-status-tone entries, and `workflowService.create`/`list` already existed from A6, unused until now. `CreateWorkflowModal` is the Create workflow CTA, shared by the page header and the "Create your first workflow" empty state: a two-field form (`workflowService.create` only needs a name), landing the new draft on US-8.2's editor route — a stub until C7, the same handoff C1 made to C2
- [x] **Workflow detail + step editor** (C7, US-8.2) — a master-detail page over the prototype's `workflow-detail.html`: `StepList` (the arrow-connected sequence, click-to-select, Add step) and `StepEditor` (PRD §15.4's seven fields for whichever step is selected, plus a Delete step behind `useConfirm()`) are two components as the PRD footnote asks, so a future drag-and-drop builder can reuse `StepList` without `StepEditor`'s form coupling. One shared `useForm`/`FormProvider` and one Save Draft / Publish pair, mirroring C4's Configuration page exactly — Publish saves the on-screen steps first, then publishes, confirmed. Add step and Delete step went beyond US-8.2's literal acceptance criteria (which only describes editing a step's existing fields): without them the editor could only ever tweak the 4-7 steps a workflow happened to seed with. `WorkflowStep.configuration`'s `Record<string, string>` — in PRD §15.4 but absent from the prototype's own step form — is a key/value row editor, a new pattern with no prior precedent in this codebase. Publishing a workflow with zero steps is blocked by a toast before the confirm dialog even opens, rather than folded into the shared validator, so a brand-new draft (landing here with no steps, straight from C6's create flow) can still be saved without being forced to add a step first. `StepEditor`'s configuration `useFieldArray` is keyed by both the step's id and its index, not either alone: react-hook-form doesn't support a dynamically-changing field-array path on one mounted instance, so anything that changes which path it points at — a different step selected, or the same step moved to a different index — must force a remount (both caught in code review, each with a reproduction). Move up/down buttons on each step (`StepList`'s `onMove`) round out reordering, added after C7 shipped once its absence surfaced in use — the PRD defers only drag-and-drop to Phase F, not reordering altogether
- [x] **Integrations catalog** (D1, US-9.1) — one card per connection over `integrationService.list()`'s ten-item seed (all five `IntegrationStatus` values, all ten PRD §17.1 categories), filterable by category via a local-state `Select` rather than URL state: a fixed ~10-card catalog has little use for a shareable filtered link, unlike Knowledge (C1) or Conversations (B6). Display only — name, category, `StatusPill`, last activity (`relativeTime`, or "No activity yet"), connected account when present, and the features using the connection, or "Not used by any feature yet". No Connect/Continue setup/Repair/Disconnect actions and no "Add integration" button: US-9.1's acceptance criteria bundles them with the catalog, but TODO.md's own split hands them to D2, the same order C1→C2 and C6→C7 took. `integrationLabels.ts` (category labels) mirrors `knowledgeLabels.ts`'s pattern of a `Record` plus a derived, compile-time-exhaustive array. Two empty states like Knowledge's: a category filtered to zero matches versus the PRD §17/US-9.1-exact "Connect your first business system" for a genuinely empty catalog
- [x] **Integration connect / repair / disconnect** (D2, US-9.1) — Connect, Continue setup, Repair connection, and Reconnect resolve from one status-keyed map (`src/lib/integrationActions.ts`); credential fields come from a second, per-category map (`src/lib/integrationAuthFields.ts`) — ten categories, each with the fields its real system would actually ask for, so the modal never shows an irrelevant field and is the one file E6 replaces once a real credential contract exists. A `secret`-typed field renders as a password input and starts empty on every path, including Repair where the account is already known — PRD §17.3 / §47 — and a submitted secret is discarded by the mock service rather than stored; a test exercises the real connect path end to end (fills the form, submits, asserts against `store.integrations`) rather than checking the field type alone. `IntegrationCard` is self-contained the way `FeatureCard` is: its own `connect`/`repair`/`disconnect` mutations, its own `useConfirm()` and toast, patching the shared `INTEGRATIONS_KEY` (`['integrations', 'list']`, now imported by `IntegrationsPage` rather than redeclared) cache on success. Disconnect's confirmation names the actual features that stop working, not a generic warning — "Inventory Lookup will stop working until StockSync is reconnected." The mock service raises no invented failure modes; `connect`/`repair` always succeed, matching every other A6 mock unless a task specifically calls for an error path. Four same-text collisions surfaced only once the flows ran end to end — the card's own Connect/Repair trigger against its modal's identically-labelled submit button, the card's own Disconnect trigger against `useConfirm()`'s identically-labelled (`confirmLabel: 'Disconnect'`) confirm button, the card's persistent "Features: …" line against the disconnect dialog's identically-worded consequence, and the connect-success toast against `StatusPill`'s "Connected" label. The Features line is a `<p>`, so it's simply omitted while its dialog is open. The two trigger buttons needed more care than that: `useFocusTrap` (`src/lib/useFocusTrap.ts`, shared by `Modal` and `useConfirm()`'s dialog) captures `document.activeElement` when a dialog opens and calls `.focus()` on that same node when it closes, so conditionally unmounting a trigger to hide it — the first attempt — detaches the very node the trap is holding onto, and silently drops focus instead of restoring it. Both triggers now stay mounted throughout, toggling `aria-hidden`/`tabIndex={-1}` instead (which is what `getByRole` and screen readers actually key off, not mount state), and each also restores its own focus explicitly on its own dialog's close — belt-and-suspenders for Disconnect in particular, since `useConfirm()`'s dialog lives in a different component (`ConfirmDialogProvider`) reacting to the same click via a resolved Promise rather than a shared state update, so nothing guarantees its close and this card's own re-render land in an order `useFocusTrap`'s restoration alone could rely on. The toast collision is resolved by rewording it to `"${name} is set up and ready."` instead of `"${name} connected."`, since a `connected` status's `StatusPill` already renders the literal word "Connected" beside it and a toast repeating it made "reports it" ambiguous for anything reading the screen by text — this is also why the connect-success test asserts against the toast's exact copy rather than a loose `/connected/i` match, which a not-yet-connected card's own "Not connected" pill text would already satisfy on mount, before Connect is even clicked. **No "Add integration" button**: the catalog is a fixed, pre-seeded set of business systems, so "add" and "connect" are the same act here — there is no separate creation step the way Knowledge or Workflows have one. Real developer-defined integrations (APIs, MCP servers, webhooks, custom tools) are PRD §17.3's Phase F item, already tracked there
- [x] **Routing rules table** (D3, US-10.1) — PRD §18.4's six columns (Rule, Condition, Destination, Schedule, Priority, Status) over `routingService.list()`'s eight-rule seed, which already sorts priority-ascending so rows read in the order the rules are actually evaluated. No filters and no pagination, the same call C6 made for the workflow list at this row count. The Status column doubles as US-10.1's inline enable/disable: `RuleStatusToggle` is self-contained like `FeatureCard` — its own mutation, patching the shared `['routing', 'rules']` query cache on success — and puts the state in words next to the switch so status never rides on colour alone. Condition and Destination are composite cells, a detail line under the label: without it a threshold rule shows no amount and a keyword rule shows no keywords. `routingLabels.ts` puts every condition, destination, and schedule in business language, mirroring `integrationLabels.ts`/`knowledgeLabels.ts`. Two summary stats, not the prototype's three: Active rules is derived from the rules query already on the page rather than a separate count, so a row's toggle moves it the instant the cache updates; Escalations today comes from `dashboardService.countEscalations`. Avg pickup is dropped — `Escalation` records when an escalation was raised, never when a person picked it up, and US-10.1 marks the stats optional, so the number is left out rather than invented. No Add rule button yet: D4 adds every write path at once, so no PR ships a button that does nothing
- [x] **Routing rule editor** (D4, US-10.1) — `RoutingRuleModal` wired into `RoutingPage` at every entry point: the page header's Add rule button, the empty state's CTA, and a per-row Edit action. `RoutingRulesTable` gained an optional `renderRowAction` slot for that last one — omitted, the table stays exactly as read-only as D3 left it. One modal handles both create and edit; six fields with no sub-collections don't justify a route, and the prototype has no routing-detail screen. Two fields follow a sibling's value: the detail field appears only for the conditions that mean nothing without one, relabelled per condition, and the destination value's label follows the destination type chosen. Priority is a plain, non-unique number with no reordering UI — unlike C7's step list, where sequence *is* the model, here rules may legitimately share a priority. Delete is the only confirmed action on this screen; the Status toggle is already undone with one click. A new rule's `defaultPriority` is set once, at the moment Add rule is clicked, rather than continuously derived from the live rules query — otherwise a background refetch while the modal was still open would re-fire the form's reset effect and silently wipe whatever the user had already typed

---

## Phase B — Operations

**Complete.** All eight tasks shipped; see the Done list above.

## Phase C — Concierge administration

**Complete.** All seven tasks shipped; see the Done list above.

---

## Phase D — Connect

**Complete.** All four tasks shipped; see the Done list above.

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
