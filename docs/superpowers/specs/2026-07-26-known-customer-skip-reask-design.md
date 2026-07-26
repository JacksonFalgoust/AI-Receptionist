# Known customers skip re-stating name/contact info

## Context

A recent change (Task 3 of the tool-call-interrupt-fix plan) added a
Booqable customer lookup at call-answering time, keyed on the caller's
phone number, purely to personalize Twilio's `welcome_greeting`. That
lookup result never reaches the actual conversation — the guide (via
GuideAnts) has no idea the caller is a known customer, so it still asks a
returning customer for their name and contact info on every reservation or
callback, exactly as it would a brand-new caller.

This spec adds that awareness to the conversation itself: when a caller is
recognized as an existing Booqable customer, the guide confirms their
known name/contact once, briefly, instead of asking for it fresh.

## Scope

Applies to both flows that currently ask for the caller's name:

- **RENTALS** (booking a reservation)
- **CALLBACKS** (buy/service/person requests)

Both `guide-demo/Demo guide with reference file/instructions.md` and
`guide-demo/Demo guide just system prompt/instructions.md` carry
near-identical copies of these two sections and both need the same edit.

Out of scope: re-doing or reusing the `/twiml` handler's greeting lookup
directly (see Data & Tool Changes below — this is a deliberate, separate
lookup).

## Data & Tool Changes

`GuideSession` (`app/guide_client.py`) gains two fields:

```python
known_customer_checked: bool = False
known_customer: dict | None = None  # raw Booqable customer record, or None
```

The `get_caller_phone_number` client-side tool's handler in `_execute_tool`
does a lazy, once-per-call lookup the first time it's invoked in a given
call:

```python
if name == "get_caller_phone_number":
    if not session.known_customer_checked:
        session.known_customer_checked = True
        if session.caller_phone:
            try:
                client = BooqableClient()
                session.known_customer = await asyncio.wait_for(
                    reservations.find_customer(client, phone=session.caller_phone),
                    timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS,
                )
            except (BooqableError, asyncio.TimeoutError, Exception):
                session.known_customer = None
    result = {"phone_number": session.caller_phone}
    if session.known_customer:
        # BooqableClient.attrs() is a @staticmethod (resource.get("attributes")
        # or {}) -- callable without an instance, so this works whether this
        # call just did the lookup above or is reusing a cached one from
        # earlier in the session.
        attrs = BooqableClient.attrs(session.known_customer)
        if attrs.get("name"):
            result["customer_name"] = attrs["name"]
        if attrs.get("email"):
            result["customer_email"] = attrs["email"]
    return json.dumps(result)
```

Notes:

- Reuses `config.CALLER_LOOKUP_TIMEOUT_SECONDS` (already added for the
  `/twiml` greeting lookup) rather than a new config knob.
- The broad `except (BooqableError, asyncio.TimeoutError, Exception)` is
  deliberate, matching the pattern already established in `_greeting_for`
  (`app/main.py`): this lookup must never raise past the tool, and must
  never prevent `phone_number` from being returned.
- The cache (`known_customer_checked`) means a call that invokes
  `get_caller_phone_number` more than once in the same session (e.g. once
  during a reservation, again later for a callback) only performs one
  Booqable lookup.
- This is a **separate lookup** from the `/twiml` handler's greeting
  lookup, not a reuse of its result — the WS session is a different HTTP
  request than `/twiml`, and threading state between them (via the signed
  ws token, or a server-side cache keyed by CallSid) was considered and
  rejected as unnecessary complexity for a single extra Booqable API call
  per call that reaches this tool.

Tool JSON result shape — `customer_name`/`customer_email` are present only
when a match is found with a non-empty name/email on file:

```json
{"phone_number": "+15551234567", "customer_name": "Jane Doe", "customer_email": "jane@example.com"}
```

```json
{"phone_number": "+15551234567"}
```

No changes to the tool's declared schema
(`guide-demo/caller-phone-client-tool.json`) are required for the guide to
see the new fields — this is a Client Actions tool, so its response schema
isn't enforced the way a Web API tool's would be; the schema's
`description` should still be updated for documentation accuracy (see
below).

## Conversational Flow Changes (system prompt)

Today, both flows ask for the caller's name *before* touching
`get_caller_phone_number`:

- RENTALS: ask name → ask "calling number or different?" → if calling
  number, call `get_caller_phone_number`.
- CALLBACKS: ask name → call `get_caller_phone_number`.

Both are reordered so `get_caller_phone_number` is called **proactively,
right when the flow starts gathering the caller's info — before asking
anything**:

- If the result includes `customer_name`: confirm briefly — e.g. *"I have
  you down as Jane Doe using this number — does that still work?"* — and
  if confirmed, use that name and phone (or email, if present) for the
  reservation/customer record without asking for them again.
- If the caller says that's not them, or wants different contact info:
  fall back to asking for name and preferred contact the normal way —
  identical to today's behavior for that case.
- If the result has no `customer_name` (no match, or the lookup
  failed/timed out): ask for name and contact the normal way — identical
  to today, no special-casing needed in the guide's own reasoning beyond
  "is `customer_name` present in the tool result."

This only ever matches on the number the caller is **currently calling
from** (that's what `get_caller_phone_number` reports on) — a caller who
wants to use a different number is asked for their name and that number
fresh, exactly as today.

Both instructions.md files' RENTALS and CALLBACKS sections get this
reordering and instruction, worded consistently with each file's existing
style (the "with reference file" version is more verbose/detailed; the
"just system prompt" version is more terse — match each file's own voice
rather than copying identical text into both).

## Error Handling

| Scenario | Behavior |
|---|---|
| Lookup raises (`BooqableError`, unexpected exception) | `customer_name`/`customer_email` omitted; `phone_number` still returned; guide asks fresh |
| Lookup exceeds `CALLER_LOOKUP_TIMEOUT_SECONDS` | Same as above |
| No customer matches the phone number | Same as above |
| Caller declines the confirmation | Guide asks for name/contact fresh, same as today |
| Caller wants a different number | Guide asks for name/contact fresh, same as today (unaffected by this change) |

## Testing

`tests/test_guide_client.py`, extending the existing
`test_execute_tool_returns_caller_phone`-style tests:

1. Known customer found (name + email on file) → result includes both
   `customer_name` and `customer_email`.
2. No match found → result has only `phone_number`.
3. Lookup raises `BooqableError` → result has only `phone_number`, no
   exception propagates.
4. Lookup exceeds the configured timeout → same graceful fallback as (3).
5. Calling `get_caller_phone_number` twice in the same `GuideSession` only
   triggers one `find_customer` call (verifies the `known_customer_checked`
   cache) — assert the mock/fake lookup's call count.

No changes needed to `createReservation`, `createCustomer`, or any other
reservation tool — this only changes what `get_caller_phone_number`
returns and what the system prompt tells the guide to do with the result.

## Out of Scope / Deliberately Not Done

- Not reusing or threading the `/twiml` handler's greeting-lookup result
  into the WS session — see Data & Tool Changes above.
- Not adding a new dedicated tool (e.g. `getKnownCustomer`) — enriching the
  existing `get_caller_phone_number` tool was chosen over a new tool
  surface, since the guide already calls it at a natural point in both
  flows.
- Not changing behavior for a caller who wants to use a different number
  than the one they're calling from.
