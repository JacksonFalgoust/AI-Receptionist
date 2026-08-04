"""Covers the trigger-phrase change: guide_client now withholds every
round's text behind a `_SentinelGate` until config.FINAL_ANSWER_SENTINEL
("declare victory" by default) has been seen in the stream, instead of
buffering a whole round (main) or a fixed character threshold
(feature/live-token-streaming). See app/guide_client.py's
_stream_reply_with_tools docstring for the full rationale.

Uses the same FakeStream/_fake_client harness as tests/test_guide_client.py,
duplicated locally rather than imported so this file's `monkeypatch`ing of
the module-level compiled sentinel patterns can't be accidentally undone by
that file's autouse fixture (which disables gating for its own tests).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from app import guide_client
from app.guide_client import GuideSession


async def _collect(aiter):
    return [item async for item in aiter]


def _texts(events) -> list[str]:
    return [e.text for e in events if isinstance(e, guide_client.Delta)]


def _tool_events(events) -> list["guide_client.ToolCallStarted"]:
    return [e for e in events if isinstance(e, guide_client.ToolCallStarted)]


class _FakeClient(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(with_options_calls=[], **kwargs)

    def with_options(self, **kwargs):
        self.with_options_calls.append(kwargs)
        return self


def _fake_client(create) -> _FakeClient:
    return _FakeClient(responses=SimpleNamespace(create=create))


class FakeStream:
    """Same as tests/test_guide_client.py's FakeStream, but the gate can be
    released per-event (an asyncio.Event that's `.set()` and `.clear()`ed
    between events by the test) rather than only all-or-nothing, so a test
    can prove text was forwarded mid-round rather than at round end."""

    def __init__(self, events, gate: asyncio.Event | None = None):
        self._events = list(events)
        self._gate = gate
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._gate is not None:
            await self._gate.wait()
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


def _bad_request_error(code: str) -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "http://test/v1/responses"))
    return openai.BadRequestError(code, response=response, body={"code": code, "message": code})


def _function_call_item(call_id: str, name: str = "checkAvailability", arguments: str = "{}"):
    return SimpleNamespace(type="function_call", call_id=call_id, name=name, arguments=arguments)


def _delta_events(*deltas: str) -> list[SimpleNamespace]:
    return [SimpleNamespace(type="response.output_text.delta", delta=d) for d in deltas]


@pytest.fixture(autouse=True)
def _real_sentinel_patterns(monkeypatch):
    """Every test in this file exercises real gating -- rebuild the compiled
    patterns from the default phrase regardless of what other test files (or
    a local .env) may have set config.FINAL_ANSWER_SENTINEL to."""
    strict, loose = guide_client._compile_sentinel_patterns("declare victory")
    monkeypatch.setattr(guide_client, "_SENTINEL_STRICT", strict)
    monkeypatch.setattr(guide_client, "_SENTINEL_LOOSE", loose)


def test_phrase_split_across_deltas_opens_gate_and_phrase_is_never_emitted(monkeypatch):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Decl", "are vic", "tory. The bike", " is available."),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession()
    reply_events = asyncio.run(_collect(guide_client.stream_reply("is the cruiser free", session)))

    assert "".join(_texts(reply_events)) == "The bike is available."
    assert "declare" not in "".join(_texts(reply_events)).lower()
    assert "victory" not in "".join(_texts(reply_events)).lower()


def test_marker_punctuation_split_into_its_own_delta_is_still_stripped(monkeypatch):
    # Regression: observed live against a real GuideAnts stream -- the model
    # emitted "Declare victory" as one delta with no trailing punctuation
    # yet, then the sentence-ending ". " arrived as the *next* delta,
    # glued onto the real answer. A gating pattern that only absorbs
    # trailing punctuation already present in the same accumulated match
    # (the original implementation) can't catch that: the gate had already
    # opened on "Declare victory" alone, so ". We have a great selection."
    # passed straight through unfiltered, leaking the marker's own
    # punctuation into the spoken reply.
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Declare victory", ". We have a great selection."),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession()
    reply_events = asyncio.run(_collect(guide_client.stream_reply("what bikes do you have", session)))

    assert _texts(reply_events) == ["We have a great selection."]


def test_text_before_phrase_is_dropped_remainder_of_matching_delta_is_emitted(monkeypatch):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events(
            "Let me think about how to phrase this. ",
            "Declare victory. Your total is twenty five dollars.",
        ),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession()
    reply_events = asyncio.run(_collect(guide_client.stream_reply("what's the price", session)))

    assert _texts(reply_events) == ["Your total is twenty five dollars."]


def test_no_hold_back_text_forwarded_mid_round_not_flushed_at_round_end(monkeypatch):
    # Events are released one at a time by the test, not all-or-nothing --
    # if guide_client buffered a whole round (main's approach) or a fixed
    # character threshold (feature/live-token-streaming's), the post-phrase
    # Delta could only ever arrive after every event in the round had been
    # released. Here it must arrive after only the matching event.
    gate = asyncio.Event()
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        SimpleNamespace(type="response.output_text.delta", delta="Declare victory. Hi"),
        SimpleNamespace(type="response.output_text.delta", delta=" there."),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    stream = FakeStream(events, gate=gate)
    create = AsyncMock(return_value=stream)
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    async def scenario():
        session = GuideSession()
        gen = guide_client.stream_reply("hi", session)
        # response.created: not gated in this harness (gate only affects
        # __anext__ on the stream), consumed to reach the first delta.
        gate.set()
        first_text = await gen.__anext__()  # "Hi" -- the phrase-bearing event's remainder
        gate.clear()  # nothing else in FakeStream is released yet
        second_task = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0)
        assert not second_task.done()  # proves nothing was pre-fetched/buffered
        gate.set()
        second_text = await second_task
        await gen.aclose()
        return first_text, second_text

    first_text, second_text = asyncio.run(scenario())
    assert first_text == guide_client.Delta("Hi")
    assert second_text == guide_client.Delta(" there.")
    assert stream.closed


def test_trailing_punctuation_and_whitespace_after_phrase_not_spoken(monkeypatch):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Declare victory:   Great news, it's in stock."),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession()
    reply_events = asyncio.run(_collect(guide_client.stream_reply("in stock?", session)))

    assert _texts(reply_events) == ["Great news, it's in stock."]


def test_final_round_with_no_phrase_flushes_as_one_burst_failsafe(monkeypatch, caplog):
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("We're open ", "nine to six ", "every day."),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession()
    with caplog.at_level("WARNING", logger="voice_receptionist.guide"):
        reply_events = asyncio.run(_collect(guide_client.stream_reply("what are your hours", session)))

    # Exactly one Delta -- the whole round arrived in a single un-gated burst.
    assert _texts(reply_events) == ["We're open nine to six every day."]
    assert sum(1 for e in reply_events if isinstance(e, guide_client.Delta)) == 1
    assert any("No trigger phrase this turn" in r.message for r in caplog.records)


def test_failsafe_strips_a_near_miss_prefix(monkeypatch):
    # "Declare victory-" (a hyphen GuideAnts didn't put whitespace after) is
    # a near miss the strict gating pattern doesn't match mid-stream, so the
    # gate never opens and this round hits the failsafe -- but the loose
    # cleanup pass must still keep the marker out of what's spoken.
    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Declare victory-here's your total, twenty dollars."),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession()
    reply_events = asyncio.run(_collect(guide_client.stream_reply("total?", session)))

    texts = _texts(reply_events)
    assert len(texts) == 1
    assert "declare" not in texts[0].lower()
    assert "victory" not in texts[0].lower()
    assert "twenty dollars" in texts[0]


def test_intermediate_round_without_phrase_is_discarded_tool_call_started_still_yielded(monkeypatch, caplog):
    round1_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Let me check ", "the helmet too."),
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[]),
        ),
    ]
    round2_events = [
        *_delta_events("Declare victory. You're all set."),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_2", output=[]),
        ),
    ]
    create = AsyncMock(side_effect=[FakeStream(round1_events), FakeStream(round2_events)])
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession(conversation_id="conv_abc")
    with caplog.at_level("INFO", logger="voice_receptionist.guide"):
        reply_events = asyncio.run(_collect(guide_client.stream_reply("book me a bike and a helmet", session)))

    assert _texts(reply_events) == ["You're all set."]
    tool_events = _tool_events(reply_events)
    assert len(tool_events) == 1
    assert any("Discarding pre-trigger narration" in r.message for r in caplog.records)


def test_intermediate_round_with_phrase_streams_and_logs_mis_bet_warning(monkeypatch, caplog):
    # The guide said the marker in a round that then still called a tool --
    # a mis-bet: whatever streamed will be cut off once the tool's answer
    # arrives. This is logged, not silently swallowed.
    round1_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Declare victory. Checking the helmet now."),
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[]),
        ),
    ]
    round2_events = [
        *_delta_events("Declare victory. You're all set."),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_2", output=[]),
        ),
    ]
    create = AsyncMock(side_effect=[FakeStream(round1_events), FakeStream(round2_events)])
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession(conversation_id="conv_abc")
    with caplog.at_level("WARNING", logger="voice_receptionist.guide"):
        reply_events = asyncio.run(_collect(guide_client.stream_reply("book me a bike and a helmet", session)))

    texts = _texts(reply_events)
    assert "Checking the helmet now." in texts
    assert "You're all set." in texts
    assert any("already-spoken text will be cut off" in r.message for r in caplog.records)


def test_max_tool_iterations_bound_speaks_last_round_instead_of_silence(monkeypatch):
    def tool_call_stream(call_id: str) -> FakeStream:
        return FakeStream(
            [
                SimpleNamespace(type="response.output_item.done", item=_function_call_item(call_id)),
                SimpleNamespace(
                    type="response.completed",
                    response=SimpleNamespace(conversation="conv_abc", id=f"resp_{call_id}", output=[]),
                ),
            ]
        )

    # The final allowed round (index _MAX_TOOL_ITERATIONS - 1) still calls a
    # tool, but carries a gated answer -- it must be spoken, not silenced,
    # since no further round will ever run.
    last_round = FakeStream(
        [
            *_delta_events("Declare victory. Here's what I found."),
            SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_last")),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(conversation="conv_abc", id="resp_last", output=[]),
            ),
        ]
    )
    streams = [tool_call_stream(f"call_{i}") for i in range(guide_client._MAX_TOOL_ITERATIONS - 1)]
    streams.append(last_round)
    create = AsyncMock(side_effect=streams)
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession(conversation_id="conv_abc")
    reply_events = asyncio.run(_collect(guide_client.stream_reply("hi", session)))

    assert _texts(reply_events) == ["Here's what I found."]
    assert create.call_count == guide_client._MAX_TOOL_ITERATIONS


def test_start_conversation_strips_phrase_and_discards_pre_tool_call_round(monkeypatch, caplog):
    # Non-streaming fallback path (session.stream_missing_conversation).
    round1_response = SimpleNamespace(
        id="resp_1",
        conversation=None,
        output_text="Let me check that for you.",
        output=[_function_call_item("call_1")],
    )
    round2_response = SimpleNamespace(
        id="resp_2",
        conversation="conv_new",
        output_text="Declare victory. It's available.",
        output=[],
    )
    create = AsyncMock(side_effect=[round1_response, round2_response])
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession(stream_missing_conversation=True)
    with caplog.at_level("INFO", logger="voice_receptionist.guide"):
        reply_events = asyncio.run(_collect(guide_client.stream_reply("is it in stock", session)))

    assert _texts(reply_events) == ["It's available."]
    tool_events = _tool_events(reply_events)
    assert len(tool_events) == 1
    assert any("Discarding pre-trigger narration" in r.message for r in caplog.records)


def test_empty_sentinel_disables_gating_control_mode(monkeypatch):
    monkeypatch.setattr(guide_client, "_SENTINEL_STRICT", None)
    monkeypatch.setattr(guide_client, "_SENTINEL_LOOSE", None)

    events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Hi ", "there, ", "no marker needed."),
        SimpleNamespace(type="response.completed", response=SimpleNamespace(conversation="conv_abc")),
    ]
    create = AsyncMock(return_value=FakeStream(events))
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession()
    reply_events = asyncio.run(_collect(guide_client.stream_reply("hi", session)))

    # Every delta streams live -- 3 separate Delta events, not one burst.
    assert _texts(reply_events) == ["Hi ", "there, ", "no marker needed."]


def test_bad_request_error_after_a_delta_reraises_instead_of_retrying(monkeypatch):
    round1_events = [
        SimpleNamespace(type="response.created", response=SimpleNamespace(conversation="conv_abc")),
        *_delta_events("Declare victory. Partial answer before it broke."),
        SimpleNamespace(type="response.output_item.done", item=_function_call_item("call_1")),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(conversation="conv_abc", id="resp_1", output=[]),
        ),
    ]
    create = AsyncMock(
        side_effect=[FakeStream(round1_events), _bad_request_error("tool_results_not_pending")]
    )
    monkeypatch.setattr(guide_client, "_get_client", lambda: _fake_client(create))

    session = GuideSession(conversation_id="conv_abc")
    with pytest.raises(openai.BadRequestError):
        asyncio.run(_collect(guide_client.stream_reply("book it", session)))

    # The id is still cleared so the *next* turn recovers fresh.
    assert session.conversation_id is None
    assert create.call_count == 2
