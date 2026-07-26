# Known Customers Skip Re-Stating Name/Contact Info Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a caller is recognized as an existing Booqable customer (matched on the number they're calling from), the guide confirms their known name/contact once instead of asking for it fresh, in both the reservation-booking and callback-request flows.

**Architecture:** Enrich the existing `get_caller_phone_number` client-side tool so its JSON result carries `customer_name`/`customer_email` when the calling number matches a known Booqable customer (a lazy, once-per-call, gracefully-degrading lookup cached on `GuideSession`); then reorder both flows' system-prompt instructions so the guide calls this tool *before* asking for the caller's name, and confirms known info instead of asking for it.

**Tech Stack:** Python 3.14, FastAPI, pytest, Booqable JSON:API v4 (via the existing `BooqableClient`/`reservations.find_customer`), GuideAnts-hosted system prompts (plain-text `instructions.md` files, no code).

**Full design context:** `docs/superpowers/specs/2026-07-26-known-customer-skip-reask-design.md` — read this if any task instruction below seems to need more background than what's given.

## Global Constraints

- Reuse `config.CALLER_LOOKUP_TIMEOUT_SECONDS` (already defined in `app/config.py` from an earlier plan) as the timeout for this new lookup — do not add a new config value.
- The lookup must never raise past `_execute_tool`, and must never prevent `phone_number` from being returned in the tool's result, regardless of Booqable being unreachable, misconfigured, slow, or returning no match.
- No changes to `createReservation`, `createCustomer`, `checkAvailability`, or any other reservation tool's implementation — only `get_caller_phone_number`'s handler and the system prompt's instructions about it change.
- This only ever matches on the number the caller is **currently calling from** — no change to what happens when a caller wants to use a different number.
- Both `guide-demo/Demo guide with reference file/instructions.md` and `guide-demo/Demo guide just system prompt/instructions.md` need the identical RENTALS/CALLBACKS wording change (their current text for these two sections is byte-identical).

---

### Task 1: Enrich `get_caller_phone_number` with known-customer info

**Files:**
- Modify: `app/guide_client.py:66-80` (`GuideSession` dataclass), `app/guide_client.py:197-218` (`_execute_tool`), and the file's imports (add `asyncio`)
- Modify: `guide-demo/caller-phone-client-tool.json` (tool schema description + response shape, documentation only — GuideAnts doesn't enforce this schema for Client Actions tools, but it must stay accurate)
- Modify: `docs/ARCHITECTURE.md:85` and `docs/ARCHITECTURE.md:170-172` (keep the `GuideSession` field list and the `get_caller_phone_number` behavior description in sync with the code)
- Test: `tests/test_guide_client.py` (modify one existing test, add four new ones)

**Interfaces:**
- Consumes: `reservations.find_customer(client, *, email=None, phone=None) -> dict | None` (already exists, `app/reservations.py:150`, unchanged); `BooqableClient()` / `BooqableClient.attrs(resource) -> dict` (already exist, unchanged); `config.CALLER_LOOKUP_TIMEOUT_SECONDS: float` (already exists, unchanged).
- Produces: `GuideSession.known_customer_checked: bool` and `GuideSession.known_customer: dict | None` (new fields, consumed by nothing outside this task — internal cache). `get_caller_phone_number`'s JSON result gains optional `customer_name: str` / `customer_email: str` keys, consumed by Task 2's system-prompt instructions (as data the guide reads from a tool result, not as a Python interface).

- [ ] **Step 1: Write the failing tests in `tests/test_guide_client.py`**

First, locate and replace the existing `test_execute_tool_returns_caller_phone` test (currently reads, unmodified, exactly as below) so it stays hermetic (this repo's local `.env` may have a real `BOOQABLE_API_KEY` configured — without an explicit monkeypatch, this test would otherwise make a real network call):

Find:
```python
def test_execute_tool_returns_caller_phone():
    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(guide_client._execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": "+15551234567"}
```

Replace with:
```python
def test_execute_tool_returns_caller_phone(monkeypatch):
    monkeypatch.setattr(guide_client.config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        return None

    monkeypatch.setattr(guide_client.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(guide_client._execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": "+15551234567"}
```

Leave `test_execute_tool_returns_null_when_caller_phone_unknown` exactly as-is (no phone number means no lookup is ever attempted — nothing to change).

Then add these four new tests directly after `test_execute_tool_returns_null_when_caller_phone_unknown`:

```python
def test_execute_tool_caller_phone_includes_known_customer_info(monkeypatch):
    monkeypatch.setattr(guide_client.config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        return {"id": "cust_1", "attributes": {"name": "Jane Doe", "email": "jane@example.com"}}

    monkeypatch.setattr(guide_client.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(guide_client._execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {
        "phone_number": "+15551234567",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
    }


def test_execute_tool_caller_phone_lookup_raises_falls_back_gracefully(monkeypatch):
    monkeypatch.setattr(guide_client.config, "BOOQABLE_API_KEY", "test-booqable-key")

    async def fake_find_customer(client, *, email=None, phone=None):
        raise RuntimeError("Booqable is down")

    monkeypatch.setattr(guide_client.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(guide_client._execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": "+15551234567"}


def test_execute_tool_caller_phone_lookup_timeout_falls_back_gracefully(monkeypatch):
    monkeypatch.setattr(guide_client.config, "BOOQABLE_API_KEY", "test-booqable-key")
    monkeypatch.setattr(guide_client.config, "CALLER_LOOKUP_TIMEOUT_SECONDS", 0.01)

    async def fake_find_customer(client, *, email=None, phone=None):
        await asyncio.sleep(0.5)
        return {"id": "cust_1", "attributes": {"name": "Jane Doe"}}

    monkeypatch.setattr(guide_client.reservations, "find_customer", fake_find_customer)

    session = GuideSession(caller_phone="+15551234567")
    result = asyncio.run(guide_client._execute_tool("get_caller_phone_number", "{}", session))
    assert json.loads(result) == {"phone_number": "+15551234567"}


def test_execute_tool_caller_phone_caches_lookup_across_calls(monkeypatch):
    monkeypatch.setattr(guide_client.config, "BOOQABLE_API_KEY", "test-booqable-key")

    find_customer_mock = AsyncMock(
        return_value={"id": "cust_1", "attributes": {"name": "Jane Doe"}}
    )
    monkeypatch.setattr(guide_client.reservations, "find_customer", find_customer_mock)

    session = GuideSession(caller_phone="+15551234567")
    first = asyncio.run(guide_client._execute_tool("get_caller_phone_number", "{}", session))
    second = asyncio.run(guide_client._execute_tool("get_caller_phone_number", "{}", session))

    assert json.loads(first)["customer_name"] == "Jane Doe"
    assert json.loads(second)["customer_name"] == "Jane Doe"
    assert find_customer_mock.call_count == 1
```

Check the top of `tests/test_guide_client.py` for how `AsyncMock` is already imported (it's used elsewhere in this file, e.g. by `test_execute_tool_list_catalog`) — reuse that same import, don't add a new one.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_guide_client.py -k "caller_phone" -v`

Expected: the four new tests FAIL (attribute/key errors — `known_customer`/`known_customer_checked` don't exist yet, and the tool result never contains `customer_name`/`customer_email`). `test_execute_tool_returns_caller_phone` and `test_execute_tool_returns_null_when_caller_phone_unknown` should still PASS unchanged (nothing about the tool's current behavior is broken yet).

- [ ] **Step 3: Add the `import asyncio` and the two new `GuideSession` fields**

In `app/guide_client.py`, add `import asyncio` to the imports (alphabetically first among the stdlib imports, before `import contextlib`):

```python
import asyncio
import contextlib
import json
import logging
```

Then add two fields to the `GuideSession` dataclass (`app/guide_client.py:66-80`), immediately after the existing `caller_phone` field:

```python
    caller_phone: str | None = None
    # Set the first time get_caller_phone_number is called this session --
    # caches whether a Booqable customer lookup for caller_phone has already
    # been attempted, so a call that invokes the tool more than once (e.g.
    # once during a reservation, again later for a callback) doesn't repeat
    # the lookup.
    known_customer_checked: bool = False
    # The matched Booqable customer record from that lookup, or None if not
    # yet checked, no match was found, or the lookup failed/timed out.
    known_customer: dict | None = None
```

- [ ] **Step 4: Implement the lookup in `_execute_tool`**

Replace the `get_caller_phone_number` branch of `_execute_tool` (`app/guide_client.py:197-202`):

Find:
```python
    if name == "get_caller_phone_number":
        return json.dumps({"phone_number": session.caller_phone})
```

Replace with:
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
                except Exception:
                    session.known_customer = None
        result: dict[str, Any] = {"phone_number": session.caller_phone}
        if session.known_customer:
            attrs = BooqableClient.attrs(session.known_customer)
            if attrs.get("name"):
                result["customer_name"] = attrs["name"]
            if attrs.get("email"):
                result["customer_email"] = attrs["email"]
        return json.dumps(result)
```

`config` is already imported at the top of this file (`from . import config, payments, reservations`) — no new import needed for it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_guide_client.py -v`

Expected: all tests in this file PASS, including the 4 new ones and the modified `test_execute_tool_returns_caller_phone`.

- [ ] **Step 6: Run the full test suite**

Run: `source .venv/bin/activate && pytest -q`

Expected: all tests pass (no regressions in other files).

- [ ] **Step 7: Update `guide-demo/caller-phone-client-tool.json`**

Replace the `description` field for the `get_caller_phone_number` operation:

Find:
```json
        "description": "Takes no arguments. Use this to get the caller's own phone number, e.g. to offer it as a reservation or callback number instead of asking for it. May return a null phone_number if it isn't available for this call.",
```

Replace with:
```json
        "description": "Takes no arguments. Use this to get the caller's own phone number, e.g. to offer it as a reservation or callback number instead of asking for it, and to check whether they're a known customer before asking for their name. May return a null phone_number if it isn't available for this call. If the calling number matches an existing customer, the response also includes customer_name and, if on file, customer_email -- confirm this info with the caller instead of asking for their name and contact info fresh.",
```

Replace the response schema's `properties` object:

Find:
```json
                  "properties": {
                    "phone_number": {
                      "type": "string",
                      "nullable": true,
                      "description": "The caller's phone number as provided by Twilio caller ID, or null if unavailable"
                    }
                  }
```

Replace with:
```json
                  "properties": {
                    "phone_number": {
                      "type": "string",
                      "nullable": true,
                      "description": "The caller's phone number as provided by Twilio caller ID, or null if unavailable"
                    },
                    "customer_name": {
                      "type": "string",
                      "description": "Present only if the calling number matches an existing Booqable customer -- their name on file"
                    },
                    "customer_email": {
                      "type": "string",
                      "description": "Present only if a matching customer was found and has an email on file"
                    }
                  }
```

- [ ] **Step 8: Update `docs/ARCHITECTURE.md`**

Update the `GuideSession` field description (`docs/ARCHITECTURE.md:85`):

Find:
```
- `GuideSession` — a small dataclass holding the call's continuation state: `conversation_id: str | None`, mutated in place by `stream_reply` as the continuation handle it gets back from GuideAnts, and `caller_phone: str | None`, set once by `app/main.py`'s `setup` handler from Twilio's `from` field and read by the `get_caller_phone_number` client-side tool (see "Client-side tool calls" below). One instance lives for the life of a call (`CallState.guide` in `app/main.py`).
```

Replace with:
```
- `GuideSession` — a small dataclass holding the call's continuation state: `conversation_id: str | None`, mutated in place by `stream_reply` as the continuation handle it gets back from GuideAnts, and `caller_phone: str | None`, set once by `app/main.py`'s `setup` handler from Twilio's `from` field and read by the `get_caller_phone_number` client-side tool (see "Client-side tool calls" below). Also `known_customer_checked: bool` and `known_customer: dict | None`, caching the result of a lazy Booqable customer lookup on `caller_phone`, done at most once per call the first time `get_caller_phone_number` is invoked. One instance lives for the life of a call (`CallState.guide` in `app/main.py`).
```

Update the `get_caller_phone_number` behavior description (`docs/ARCHITECTURE.md:170-172`):

Find:
```
    it resolves each via `_execute_tool` — `get_caller_phone_number` just
    returns `json.dumps({"phone_number": session.caller_phone})` (`null` if
    the `setup` message never carried a `from`); the seven reservation tool
```

Replace with:
```
    it resolves each via `_execute_tool` — `get_caller_phone_number` returns
    `json.dumps({"phone_number": ...})` (`null` if the `setup` message never
    carried a `from`), plus `customer_name`/`customer_email` if a lazy,
    once-per-call Booqable lookup on that phone number (cached on
    `GuideSession.known_customer`, bounded by
    `config.CALLER_LOOKUP_TIMEOUT_SECONDS`, degrading silently to no match on
    any failure) finds an existing customer; the seven reservation tool
```

- [ ] **Step 9: Run the full test suite again**

Run: `source .venv/bin/activate && pytest -q`

Expected: all tests still pass (the `.json` and `.md` edits don't affect any Python test, this just confirms nothing was accidentally broken while editing nearby).

- [ ] **Step 10: Commit**

```bash
git add app/guide_client.py guide-demo/caller-phone-client-tool.json docs/ARCHITECTURE.md tests/test_guide_client.py
git commit -m "Enrich get_caller_phone_number with known-customer info from Booqable"
```

---

### Task 2: Update system prompts to skip re-asking known customers

**Files:**
- Modify: `guide-demo/Demo guide with reference file/instructions.md` (RENTALS and CALLBACKS paragraphs)
- Modify: `guide-demo/Demo guide just system prompt/instructions.md` (RENTALS and CALLBACKS paragraphs — currently byte-identical to the other file's versions of these two paragraphs)

**Interfaces:**
- Consumes: the `get_caller_phone_number` tool's enriched JSON result from Task 1 (`phone_number`, optional `customer_name`, optional `customer_email`) — as prose instructions to the guide, not a Python interface.
- Produces: nothing consumed by other tasks — this is the last task in this plan.

There is no automated test for system-prompt wording (these are plain-text files read by GuideAnts, not code) — verification for this task is the full existing test suite still passing (confirming the edits didn't corrupt anything else) plus a manual read-through of the new wording against the checklist in Step 3.

- [ ] **Step 1: Update the RENTALS paragraph in both files**

In **both** `guide-demo/Demo guide with reference file/instructions.md` and `guide-demo/Demo guide just system prompt/instructions.md`, within the RENTALS paragraph, find this exact sentence pair:

Find:
```
To create the reservation you need the caller's full name, plus their email or their phone number. For the phone number, ask the caller whether they'd like to use the number they're calling from or a different number — if they want the number they're calling from, use the get_caller_phone_number tool to get it; if they want to use a different number, ask them to give it to you.
```

Replace with:
```
To create the reservation you need the caller's full name, plus their email or their phone number. Before asking for either one, call the get_caller_phone_number tool — if it returns a customer_name, the caller is a known customer, so confirm it with them, for example by asking whether you still have them down as that name using the number they're calling from, instead of asking for their name outright. If they confirm, use that name and the phone number from the tool, or their known email if the tool included one, for the reservation without asking again. If they say that's not them, or they'd rather use different contact information, ask for their full name, then ask whether they'd like to use the number they're calling from or a different number — if they want the number they're calling from, use the phone number you already have from the tool; if they want a different number, ask them to give it to you. If get_caller_phone_number doesn't return a customer_name, just ask for their full name, then ask whether they'd like to use the number they're calling from or a different number the same way.
```

This sentence pair is identical in both files (confirm with `grep -n "For the phone number, ask the caller" "guide-demo/Demo guide with reference file/instructions.md" "guide-demo/Demo guide just system prompt/instructions.md"` before editing — both should match), so the same replacement text applies to both.

- [ ] **Step 2: Update the CALLBACKS paragraph in both files**

In **both** files, within the CALLBACKS paragraph, find:

Find:
```
Ask for their name. Then use the get_caller_phone_number tool to get the number they're calling from and use that as the callback number, without asking them for it — only ask them for a number if the tool doesn't return one.
```

Replace with:
```
Call the get_caller_phone_number tool first — if it returns a customer_name, confirm it with them, for example by asking whether you still have them down as that name using the number they're calling from, instead of asking for their name outright. If they confirm, use that name and the phone number from the tool as their callback info without asking again. If they say that's not them, ask for their name instead, and still use the phone number from the tool as the callback number without asking for it separately — only ask them for a number if the tool doesn't return one. If get_caller_phone_number doesn't return a customer_name, ask for their name, then use the phone number from the tool as the callback number the same way.
```

- [ ] **Step 3: Manual review checklist**

Read through both updated files in full and confirm:
- Neither file introduces any markdown, bullet points, numbered lists, bold/italic markup, or symbols (matches the existing "Never use markdown..." instruction at the top of both files).
- The new wording reads as natural spoken sentences a receptionist would actually say out loud (matches the existing style of the rest of the document).
- The RENTALS and CALLBACKS paragraphs remain single paragraphs (no accidental line breaks introduced).
- Nothing else in either file changed (diff the files against the previous commit and confirm only the two target sentences changed per file).

- [ ] **Step 4: Run the full test suite**

Run: `source .venv/bin/activate && pytest -q`

Expected: all tests pass (these are `.md` files, not imported by any test — this confirms nothing else was accidentally touched).

- [ ] **Step 5: Commit**

```bash
git add "guide-demo/Demo guide with reference file/instructions.md" "guide-demo/Demo guide just system prompt/instructions.md"
git commit -m "Have both flows check for a known customer before asking for name/contact"
```

---

## Self-Review Notes

- **Spec coverage:** Data & Tool Changes → Task 1 (Steps 1-6 for the code/tests, Steps 7-8 for docs). Conversational Flow Changes → Task 2. Error Handling table → covered by Task 1's 4 new tests (raises, timeout, no-match via the modified existing test, and the caller-wants-different-number/declines-confirmation cases which are prose-only, covered in Task 2's wording). Testing section's 5 scenarios → Task 1's tests (found/no-match/raises/timeout/cache — no-match is folded into the modified `test_execute_tool_returns_caller_phone` rather than duplicated, since that's exactly what it already asserts once monkeypatched to a hermetic `None`-returning fake). Out of Scope section → nothing in this plan reintroduces those (no new tool, no cross-request state threading).
- **Placeholder scan:** no TBD/TODO; every step has literal find/replace text or literal code, not a description of what to do.
- **Type consistency:** `GuideSession.known_customer: dict | None` (Task 1) matches how it's read in Task 1's own `_execute_tool` change — no other task reads this field directly (Task 2 only changes prose, not code), so there's no cross-task signature to keep in sync.
- **Improvement over the spec's own pseudocode:** the spec's sketch used `except (BooqableError, asyncio.TimeoutError, Exception)`, which the previous plan's final review flagged as a redundant tuple (the first two are already subclasses of `Exception`). This plan uses a plain `except Exception:` instead — same behavior, without repeating a defect already caught once this session.
