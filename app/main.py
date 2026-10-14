"""Twilio Conversation Relay <-> GuideAnts voice receptionist middleware.

POST /twiml   Twilio calls this when a call comes in; returns TwiML that opens
              a Conversation Relay WebSocket back to this server.
WS   /ws      Conversation Relay's WebSocket bridge: receives transcribed
              caller speech and streams the GuideAnts guide's reply back as
              speakable text tokens.

Conversation Relay is configured `interruptible="none"`, so Twilio itself
never pauses TTS playback on caller speech; it still arrives here as
"prompt" messages (`report_input_during_agent_speech="speech"`). Most
mid-reply speech (statements, backchannel, noise) is logged but not acted
on. The exception is a trigger utterance -- a stop/wait phrase or a new
question, per barge_in.should_interrupt() -- which cancels the in-flight
reply. A stop/wait phrase (barge_in.is_stop_command()) then just gets a
short local acknowledgment (config.STOP_ACK_PHRASES) and silence -- never
routed through GuideAnts, so it cuts over immediately with no extra
round-trip and doesn't depend on the guide choosing to reply briefly. A new
question instead starts a fresh reply for what the caller just said, same
as any other prompt. Playback is actually cut over using Conversation
Relay's per-frame `preemptible` flag (see respond_to()), not Twilio-native
interruption. Whether speech counts as "mid-reply" at all is tracked by
holding the reply task open until Twilio's agent-stopped speaker event
(`events="speaker-events"`, see speaker_events.py) reports playback
finished, falling back to a word-count estimate of the speaking time
(speech_timing.py) until the first such event is recognized on the call.
Every `Delta` this module receives from guide_client.stream_reply() is already gated: the guide
is instructed to open its final answer with a fixed trigger phrase
(config.FINAL_ANSWER_SENTINEL, see guide-demo/template/instructions.template.md's "FINAL
ANSWER MARKER" paragraph and guide_client._SentinelGate), and nothing reaches this module until
that phrase has been seen and stripped -- so respond_to() can forward every delta to Twilio the
instant it arrives with no local buffering of its own. This is why a reply can go quiet for a
while (narration ahead of a tool call, or the model's own "thinking" -- see
docs/THINKING_LEAK_FIXES.md -- both held back by the gate rather than spoken and cut off) and
then start streaming mid-sentence rather than only ever between rounds. When a caller's
utterance looks like a question or request (see fillers.py) and GuideAnts' reply doesn't arrive
within config.FILLER_DELAY_SECONDS, a short filler phrase is spoken while still waiting on the
same in-flight call, to mask that gated silence -- but only if Twilio doesn't still have
unplayed audio queued from what's already been sent this turn, so a filler can't stack on top of
speech the guide just produced. This isn't limited to the very first wait: every fetch of the
next event races the same timeout, so a reply that runs a client-side tool call (which can go
quiet for several seconds of real tool latency -- see guide_client.ToolCallStarted) may speak
more than one filler phrase in sequence rather than leaving the caller in true silence. A tool
call in flight also softens barge-in for that gap (config.TOOL_CALL_BARGE_IN_GRACE_SECONDS):
non-stop-command speech is ignored instead of being treated as a new question that cancels the
still-pending answer.

Twilio finalizes a "prompt" at each pause in caller speech, so one spoken
turn can arrive as several prompt messages. Prompts that would start a new
turn are therefore buffered (schedule_turn()) and committed only after
config.TURN_PAUSE_SECONDS of continued caller silence, with the
clientSpeaking speaker events holding the buffer open while the caller is
still (or again) audibly speaking -- so a caller can take a brief breath
mid-sentence without the first half being answered and the second half
ignored. Stop/wait phrases are exempt: they still cut playback immediately.

Conversation memory lives server-side in GuideAnts, keyed by a conversation
id captured on the call's first turn (see guide_client.GuideSession) and
passed back as the `conversation` parameter on every later turn -- so only
the caller's latest utterance is ever sent, never a resent transcript.
`st.messages` below is therefore just a local log of what was actually
said; nothing about GuideAnts continuation depends on its contents. It is
also, as of app/call_recording.py, the source /api/conversations persists
as a call's transcript once the call ends. When a barge-in cuts a reply
short, the text the caller actually heard is folded into the next turn's
input (guide_client.build_input) so the guide knows not to repeat itself
-- see ARCHITECTURE.md's
"Interruption notes" section for how that works and its known rough edges.
"""

import asyncio
import contextlib
import json
from pathlib import Path
import logging
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from twilio.twiml.voice_response import Connect, VoiceResponse

from . import barge_in, config, fillers, reservations, speaker_events, speech_timing, twilio_auth
from . import call_recording
from .auth_api import router as auth_router
from .booqable_client import BooqableClient, BooqableError
from .concierge_api import router as concierge_router
from .conversations_api import router as conversations_router
from .dashboard_api import router as dashboard_router
from . import call_end
from .spoken_text import PhraseJoiner, canned_goodbye_text
from .db import init_db
from . import guide_client, stt_fixups
from .guide_client import Delta, GuideSession, ToolCallStarted, build_input, stream_reply
from .knowledge_api import router as knowledge_router
from .reservations_api import router as reservations_router
from .workflow_api import router as workflow_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s:%(name)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("voice_receptionist")


def mask_phone(value: str | None) -> str:
    """Log-safe phone: keep only the last 4 digits."""
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return f"***{digits[-4:]}" if len(digits) >= 4 else ("***" if value else "none")


async def _warm_up_guide() -> None:
    """One throwaway GuideAnts turn at startup so the first real call's first
    reply isn't a cold start (4.3s seen on the first call after a reboot).
    Never raises; failures are only logged."""
    try:
        t0 = asyncio.get_event_loop().time()
        async for _ in stream_reply("(system warm-up, no caller) Say OK.", GuideSession()):
            pass
        logger.info("GuideAnts warm-up done in %.2fs", asyncio.get_event_loop().time() - t0)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("GuideAnts warm-up failed: %s", type(exc).__name__)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    # E6 slice 1: creates the SQLite tables (conversations, auth_sessions,
    # ...) on startup if they don't already exist -- see app/db.py's
    # init_db(). FastAPI's docs recommend a lifespan context manager over
    # the deprecated @app.on_event("startup") handler for fastapi>=0.115
    # (confirmed via find-docs against the pinned version).
    init_db()
    warmup = asyncio.create_task(_warm_up_guide()) if config.GUIDE_WARMUP_ON_STARTUP else None
    yield
    if warmup and not warmup.done():
        warmup.cancel()


app = FastAPI(lifespan=_lifespan)
app.include_router(reservations_router)
app.include_router(auth_router)
app.include_router(concierge_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)
app.include_router(knowledge_router)
app.include_router(workflow_router)

# Ceiling on holding a buffered turn while the caller is (per clientSpeaking
# events) still audibly speaking. Normally the commit timer is re-armed by
# the coming clientSpeaking-stop event or continuation prompt long before
# this elapses; it only fires if a stop event is lost, so a stuck "on" can't
# hold the turn open forever.
PENDING_TURN_CEILING_SECONDS = 10.0

# Below this, respond_to()'s reply-token frames are logged as having reached
# Twilio in one burst rather than incrementally -- kept in sync by eye with
# scripts/check_streaming.py's _INCREMENTAL_SPAN_THRESHOLD_SECONDS (same
# idea, applied to the app -> Twilio leg instead of GuideAnts -> app).
_STREAM_TO_TWILIO_BURST_THRESHOLD_SECONDS = 0.05


def _published_greeting() -> str:
    """The greeting from the last SUCCEEDED publish, or the configured
    default. Reading the published snapshot rather than the live
    configuration row is what preserves draft semantics: editing a greeting
    in the console must not change what callers hear until Publish.

    Wrapped in a broad try like the rest of this function's lookups -- it
    sits in the call-answering path, and a database problem must never
    delay answering the phone."""
    try:
        from . import db as db_module
        from .guide_publish import publisher

        session = db_module.SessionLocal()
        try:
            publication = publisher.latest_succeeded(session)
            if publication:
                greeting = (publication.published_config or {}).get("identity", {}).get(
                    "greeting"
                )
                if greeting:
                    return greeting
        finally:
            session.close()
    except Exception:  # noqa: BLE001 -- never block answering a call
        logger.warning("could not read published greeting; using the default", exc_info=True)
    return config.WELCOME_GREETING


async def _greeting_for(from_number: str) -> str:
    """Personalize the welcome greeting for a known Booqable customer, by
    caller phone number. Falls back to the published greeting (or the plain
    WELCOME_GREETING if nothing has been published) on any failure -- this
    sits directly in the call-answering path (Twilio expects a prompt TwiML
    response), so a slow/unreachable Booqable or an unset BOOQABLE_API_KEY
    (which makes BooqableClient() itself raise immediately, see
    booqable_client.py) must never delay or break answering the call."""
    if not from_number:
        return _published_greeting()
    try:
        client = BooqableClient()
        customer = await asyncio.wait_for(
            reservations.find_customer(client, phone=from_number),
            timeout=config.CALLER_LOOKUP_TIMEOUT_SECONDS,
        )
        if not customer:
            return _published_greeting()
        name = (client.attrs(customer).get("name") or "").split()
        if not name:
            return _published_greeting()
        return config.WELCOME_BACK_GREETING_TEMPLATE.format(name=name[0])
    except (BooqableError, asyncio.TimeoutError, Exception):
        logger.warning("Caller lookup failed; using default greeting", exc_info=True)
        return _published_greeting()


_WORKING_SOUND_FILE = Path(__file__).parent / "static" / "working.mp3"


@app.get(config.WORKING_SOUND_PATH)
async def working_sound() -> FileResponse:
    """Public, static, non-sensitive: the soft 'working' loop Twilio fetches."""
    return FileResponse(_WORKING_SOUND_FILE, media_type="audio/mpeg")


@app.post("/twiml")
async def twiml(request: Request) -> Response:
    """Return TwiML that connects the call to our Conversation Relay WebSocket."""
    if not await twilio_auth.validate_twiml_request(request):
        return Response(status_code=403)

    host = request.headers.get("host", request.url.hostname)
    form = await request.form()
    call_sid = form.get("CallSid", "")
    token = twilio_auth.mint_ws_token(call_sid)
    greeting = await _greeting_for(form.get("From", ""))

    vr = VoiceResponse()
    connect = Connect()
    connect.conversation_relay(
        url=f"wss://{host}/ws?token={token}",
        welcome_greeting=greeting,
        tts_provider="ElevenLabs",
        transcription_provider="Deepgram",
        **({"hints": config.STT_HINTS} if config.STT_HINTS else {}),
        speech_model=config.STT_SPEECH_MODEL,
        language=config.STT_LANGUAGE,
        interruptible="none",
        # The welcome greeting has its own interruptibility setting, separate
        # from `interruptible` -- without this, Twilio cuts the greeting off
        # whenever it detects caller-side audio during it (including echo of
        # the greeting itself picked up on speakerphone) and sends an
        # `interrupt` message. Observed on real calls before this was set.
        welcome_greeting_interruptible="none",
        report_input_during_agent_speech="speech",
        events="speaker-events",
    )
    vr.append(connect)
    # Reached when the app ends the ConversationRelay session (endCall).
    vr.hangup()

    return Response(content=str(vr), media_type="application/xml")


@dataclass
class CallState:
    guide: GuideSession = field(default_factory=GuideSession)
    messages: list = field(default_factory=list)  # local log only, see module docstring
    # Wall-clock time this call began -- used only by call_recording.record_call()
    # to compute duration and approximate per-message timestamps when the
    # call ends; nothing in the call-flow state machine itself reads this.
    started_at: datetime = field(default_factory=datetime.utcnow)
    task: object = None  # asyncio.Task | None
    partial_reply: str = ""  # real reply text streamed so far this turn (never the filler)
    # Text of a reply the caller was actually cut off mid-way through by a
    # barge-in, if any -- folded into the *next* start_reply()'s input via
    # build_input(), then cleared. None means the previous turn (if any)
    # completed normally (or was interrupted before any of it was heard).
    interrupted_reply: str | None = None
    # The fully-generated reply currently being spoken by Twilio during
    # respond_to()'s playback hold, and when that playback (approximately)
    # started. Used to *estimate* how much the caller heard when a barge-in
    # lands during the hold -- st.partial_reply is already cleared by then,
    # and with a model that returns the whole reply in one burst (see
    # ARCHITECTURE.md) the hold is where nearly every real barge-in lands.
    playback_text: str = ""
    playback_start: float = 0.0
    # Set by the WS loop when an agent-stopped speaker event arrives
    # (events="speaker-events"); awaited by respond_to()'s playback hold.
    playback_done: asyncio.Event = field(default_factory=asyncio.Event)
    # True once any agent-stop event has been recognized this call. Until
    # then the hold uses the word-count estimate alone, so an account/shape
    # that never emits recognizable events behaves exactly as before.
    agent_stop_seen: bool = False
    # Caller text transcribed but not yet committed as a turn, plus the timer
    # task that will commit it (see schedule_turn()). Twilio finalizes a
    # prompt at each brief pause, so one spoken turn can arrive as several
    # prompt messages; these hold the fragments together until the caller has
    # actually stopped talking.
    pending_text: str = ""
    pending_commit: object = None  # asyncio.Task | None
    # Whether the caller is currently speaking, per the clientSpeaking
    # speaker events. Stays False if those events never arrive (or aren't
    # recognized), so such a call degrades to the plain TURN_PAUSE_SECONDS
    # debounce instead of misbehaving.
    client_speaking: bool = False
    # True once the guide's most recently completed reply ended in a
    # question -- e.g. "Would you like the 9am slot?" -- awaiting the
    # caller's answer. fillers.is_backchannel() would otherwise swallow a
    # short affirmative ("yeah", "yep", ...) that's actually the caller
    # answering that question, since to is_backchannel() it looks identical
    # to the late-STT trailing acknowledgment it exists to catch (see
    # ARCHITECTURE.md). Reset before each new reply starts, so a barge-in
    # that cancels a reply before it completes can't leave a stale question
    # flag from an earlier, unrelated turn in place.
    guide_awaiting_answer: bool = False
    bare_greeting_ignored: bool = False
    # event-loop-clock timestamp of the last reply's final Twilio frame
    # (the closing `last: true` message) finishing its send -- diagnostic
    # only, see respond_to()'s TIMING logs. Lets the agent-start speaker
    # event handler below report how long after that Twilio actually began
    # playback, the closest thing to a receipt Twilio gives back (there is
    # no application-level ack for individual text frames). 0.0 means no
    # reply has finished sending yet this call.
    last_reply_sent_at: float = 0.0
    # Event-loop time the *current* reply's first frame went to Twilio (0.0
    # once its agent-start has been reported, or before any frame). The
    # agent-start handler measures against this, not last_reply_sent_at: a
    # streamed reply's playback starts before its last frame is sent, so
    # measuring from "last frame" picked up the previous turn's timestamp.
    reply_first_frame_at: float = 0.0
    # Event-loop time of the caller's most recent client-stop speaker event.
    client_stop_at: float = 0.0
    # Working-sound bookkeeping for the current reply: a play message was
    # sent, and reply text has since gone out. If Twilio only starts the
    # sound after that (mediaPlaying on), it is cut immediately.
    working_play_sent: bool = False
    # Event-loop time of the latest chime `play` sent, and of the latest
    # agent-start speaker event (for stuck-audio detection).
    working_play_sent_at: float = 0.0
    last_agent_start_at: float = 0.0
    # Set after a stuck-audio recovery: no more chimes this call.
    chime_disabled: bool = False
    # Last filler phrase spoken this call, so the next one differs.
    last_filler: str | None = None
    reply_text_after_play: bool = False
    # Event-loop time a client-side tool call started this turn, or 0.0 if
    # none is currently pending. guide_client streams every round's text
    # live, including narration ahead of a tool call, so the guide can go
    # quiet mid-turn while the tool runs -- sounding like a finished reply.
    # The `prompt` handler uses this (bounded by
    # config.TOOL_CALL_BARGE_IN_GRACE_SECONDS) to keep a caller who talks
    # into that silence from cancelling the answer that's still coming.
    tool_call_started_at: float = 0.0


@app.websocket("/ws")
async def conversation_relay_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    token = websocket.query_params.get("token", "")

    st = CallState()
    public_host = websocket.headers.get("host", "")
    working_sound_url = f"https://{public_host}{config.WORKING_SOUND_PATH}" if public_host else ""

    async def _recover_stuck_audio(reply_text: str, sent_from: float) -> bool:
        """Twilio gives no ack for text frames; its agent-start speaker event is
        the only sign playback began. If none arrives within
        STUCK_AUDIO_RECOVERY_SECONDS -- after the chime `play`, if one was sent
        this turn, otherwise after the reply's first frame -- the TTS queue is
        treated as stuck (seen 2026-10-13: a chime that Twilio never fetched
        silenced every later reply). Resend the reply as a fresh talk cycle,
        which preempts the stuck media, and stop using the chime this call."""
        wait = config.STUCK_AUDIO_RECOVERY_SECONDS
        # Only once Twilio has shown it sends speaker events on this call
        # (the greeting's agent-start), so a missing event stream can't
        # cause spurious resends.
        if wait <= 0 or not st.last_agent_start_at:
            return False
        # Only a pending chime has ever stalled Twilio's queue. On other turns
        # the reply often plays straight on from the filler with no fresh
        # agent-start, which looked "stuck" and caused a repeated reply
        # (2026-10-13 09:22 call).
        if not st.working_play_sent:
            return False
        loop = asyncio.get_event_loop()
        since = st.working_play_sent_at if st.working_play_sent else sent_from
        deadline = loop.time() + wait
        while loop.time() < deadline:
            if st.last_agent_start_at >= since:
                return False
            await asyncio.sleep(0.05)
        if st.last_agent_start_at >= since:
            return False
        logger.warning(
            "No Twilio playback %.1fs after reply%s; resending without chime",
            wait, " (chime pending)" if st.working_play_sent else "",
        )
        st.chime_disabled = True
        st.working_play_sent = False
        st.reply_text_after_play = False
        await websocket.send_json(
            {"type": "text", "token": reply_text, "last": True, "preemptible": True}
        )
        return True

    async def respond_to(input_text: str, filler_eligible: bool) -> None:
        # Every frame is marked preemptible so that if this turn is still
        # playing when a later trigger-interrupted turn starts, Twilio drops
        # this audio and switches to the new turn's audio immediately. This
        # is a no-op in the normal (non-interrupting) case, since by the
        # time a new turn starts normally the previous one has already
        # finished.
        start_time = asyncio.get_event_loop().time()
        reply_text = ""
        filler = None
        tool_call_seen = False
        slow_tool_seen = False
        tool_names: tuple = ()
        after_tool = False
        working_sound_on = False
        # The caller said something new, so any earlier endCall is void.
        st.guide.end_call_requested = False
        st.working_play_sent = False
        st.reply_text_after_play = False
        audio_started_at: float | None = None
        gen = stream_reply(input_text, st.guide)
        pending: asyncio.Future | None = None
        # Diagnostic timestamps for how this reply is handed to Twilio --
        # see the TIMING/RESULT logs below and check_streaming_proxy.py's
        # module docstring for the GuideAnts-side half of this picture.
        twilio_send_start: float | None = None
        twilio_frame_count = 0
        joiner = PhraseJoiner(config.SPOKEN_JOIN_PHRASES)

        def _queued_audio_seconds() -> float:
            """Best-effort estimate of TTS audio still unplayed from what's
            already been sent this turn -- the caller isn't sitting in
            silence while this is positive, so a canned filler would just
            stack on top of speech already in flight (narration ahead of a
            tool call, or an earlier filler). Estimated from the whole
            accumulated reply_text, never by summing per-delta estimates --
            speech_timing.estimate_seconds splits on whitespace, so a delta
            split mid-word would be double-counted as two words."""
            if audio_started_at is None:
                return 0.0
            spoken = f"{filler} {reply_text}" if filler else reply_text
            played = asyncio.get_event_loop().time() - audio_started_at
            return max(
                0.0, speech_timing.estimate_seconds(spoken, config.TTS_WORDS_PER_SECOND) - played
            )

        # Only utterances that look like a question/request (see fillers.py)
        # are filler-eligible at all. Among those, race every fetch of the
        # next event from GuideAnts against the filler delay: if it's already
        # back within FILLER_DELAY_SECONDS, or Twilio still has queued audio
        # from what's already been sent this turn, skip the filler for that
        # wait; otherwise speak one and keep waiting on the same in-flight
        # fetch. This isn't limited to the first event -- a reply that runs
        # a client-side tool call can go quiet for several seconds of real
        # tool latency (see guide_client.ToolCallStarted), and each
        # sufficiently slow wait (with nothing already queued to cover it)
        # gets its own filler, so the caller is never sitting in true
        # silence for long.
        async def next_event():
            nonlocal pending, filler, tool_call_seen, working_sound_on, tool_names
            pending = asyncio.ensure_future(gen.__anext__())
            # Known-slow tools always get the filler (+ working sound), even
            # when the caller's turn wasn't a question ("Yes." before a booking).
            if (filler_eligible or slow_tool_seen) and (
                tool_call_seen or not config.FILLER_ONLY_FOR_TOOL_CALLS
            ):
                done, _ = await asyncio.wait({pending}, timeout=config.FILLER_DELAY_SECONDS)
                if (pending not in done and _queued_audio_seconds() <= 0.0 and not working_sound_on
                        and not reply_text.strip()):
                    phrase = fillers.pick_for_tools(
                        tool_names, config.FILLER_PHRASES, st.last_filler,
                        use_action_pools=config.FILLER_PHRASES == config._DEFAULT_FILLER_PHRASES,
                    )
                    if phrase:
                        st.last_filler = phrase
                    play_working = bool(
                        slow_tool_seen and config.WORKING_SOUND_ENABLED and working_sound_url
                        and not st.chime_disabled
                    )
                    if phrase:
                        filler = phrase
                        if not st.reply_first_frame_at:
                            st.reply_first_frame_at = asyncio.get_event_loop().time()
                        await websocket.send_json(
                            {"type": "text", "token": phrase + " ", "last": False, "preemptible": True}
                        )
                    if play_working:
                        working_sound_on = True  # one attempt per wait
                        # Only once the filler has finished playing, and only
                        # if the answer still isn't back: then a one-shot
                        # ~8s chime (no loop), so it can never run on.
                        filler_secs = (
                            speech_timing.estimate_seconds(phrase, config.TTS_WORDS_PER_SECOND) + 0.3
                            if phrase else 0.0
                        )
                        done, _ = await asyncio.wait({pending}, timeout=filler_secs)
                        if pending not in done:
                            await websocket.send_json(
                                {"type": "play", "source": working_sound_url, "loop": 1,
                                 "preemptible": True, "interruptible": True}
                            )
                            st.working_play_sent = True
                            st.working_play_sent_at = asyncio.get_event_loop().time()
                            st.reply_text_after_play = False
                            logger.info("Working sound started (tool wait)")
            try:
                return await pending
            except StopAsyncIteration:
                return None

        try:
            while True:
                event = await next_event()
                if event is None:
                    break
                if isinstance(event, ToolCallStarted):
                    if held := joiner.flush():
                        await websocket.send_json(
                            {"type": "text", "token": held, "last": False, "preemptible": True}
                        )
                        reply_text += held
                        st.partial_reply = reply_text
                    # The guide (or narration ahead of it) may already have
                    # gone quiet by the time this arrives -- the caller
                    # hears silence until the next Delta, which can be
                    # several seconds away (real tool-call latency). This
                    # softens barge-in for that gap; see the `prompt`
                    # handler below.
                    st.tool_call_started_at = asyncio.get_event_loop().time()
                    tool_call_seen = True
                    tool_names = tuple(event.names)
                    if set(event.names) & config.WORKING_SOUND_TOOLS:
                        slow_tool_seen = True
                    logger.info("Client tool call(s) in flight: %s", ", ".join(event.names))
                    after_tool = True
                    continue
                if after_tool:
                    # Every frame is preemptible, so text arriving after a
                    # tool call would cut off whatever is still playing (the
                    # filler or words spoken before the tool) mid-sentence.
                    # Let that finish first (bounded).
                    after_tool = False
                    waited = 0.0
                    while _queued_audio_seconds() > 0.05 and waited < 10.0:
                        await asyncio.sleep(0.05)
                        waited += 0.05
                st.tool_call_started_at = 0.0
                working_sound_on = False  # this text preempts the sound
                if st.working_play_sent:
                    st.reply_text_after_play = True
                token = joiner.feed(event.text)
                if not token:
                    continue  # held: part of a protected phrase still arriving
                if reply_text and not reply_text[-1].isspace() and not token[:1].isspace():
                    # Round boundary (e.g. narration, then a tool call, then
                    # the final answer): without this, adjacent rounds run
                    # together into "for you.It's available" in both the
                    # TTS and the interruption note built from
                    # st.partial_reply.
                    token = " " + token
                if twilio_send_start is None:
                    twilio_send_start = asyncio.get_event_loop().time()
                    st.reply_first_frame_at = twilio_send_start
                    logger.info(
                        "TIMING: GuideAnts request sent -> first token ready to send to Twilio: %.3fs",
                        twilio_send_start - start_time,
                    )
                await websocket.send_json(
                    {"type": "text", "token": token, "last": False, "preemptible": True}
                )
                twilio_frame_count += 1
                if audio_started_at is None:
                    audio_started_at = asyncio.get_event_loop().time()
                reply_text += token
                st.partial_reply = reply_text
            if held := joiner.flush():
                if twilio_send_start is None:
                    twilio_send_start = asyncio.get_event_loop().time()
                    st.reply_first_frame_at = twilio_send_start
                await websocket.send_json({"type": "text", "token": held, "last": False, "preemptible": True})
                twilio_frame_count += 1
                if audio_started_at is None:
                    audio_started_at = asyncio.get_event_loop().time()
                reply_text += held
                st.partial_reply = reply_text
            await websocket.send_json({"type": "text", "token": "", "last": True, "preemptible": True})
            if reply_text and twilio_send_start is not None:
                await _recover_stuck_audio(reply_text, twilio_send_start)
            if twilio_send_start is not None:
                # "last frame sent" is the honest number here -- Twilio gives
                # no application-level ack that it received a text frame, so
                # this is when *we* finished handing the reply over, not
                # confirmation Twilio has it. The agent-start speaker-event
                # handler below reports the closest thing to a receipt
                # Twilio actually gives back.
                st.last_reply_sent_at = asyncio.get_event_loop().time()
                span = st.last_reply_sent_at - twilio_send_start
                logger.info(
                    "TIMING: first frame sent to Twilio -> last frame (incl. end-of-turn) sent: %.3fs (%d frames)",
                    span, twilio_frame_count,
                )
                if span < _STREAM_TO_TWILIO_BURST_THRESHOLD_SECONDS:
                    logger.info("RESULT: reply handed to Twilio as one burst (%.3fs apart) -- not incremental.", span)
                else:
                    logger.info("RESULT: reply handed to Twilio incrementally, spread over %.3fs.", span)
        except asyncio.CancelledError:
            if pending:
                pending.cancel()
                with contextlib.suppress(Exception):
                    await pending
            # Ensure the underlying SSE response (if any) is closed before
            # the interrupting turn's request goes out, rather than at GC
            # time -- avoids a stale socket overlapping the next request on
            # the shared connection pool.
            with contextlib.suppress(Exception):
                await gen.aclose()
            raise
        except Exception:
            logger.exception("Error while streaming guide reply")
            try:
                await websocket.send_json(
                    {
                        "type": "text",
                        "token": "Sorry, I'm having trouble right now.",
                        "last": True,
                        "preemptible": True,
                    }
                )
            except Exception:
                pass
            return
        finally:
            # Cleared on every exit -- cancellation, error, or normal
            # completion -- so a stale window can never leak into whatever
            # happens next on this call.
            st.tool_call_started_at = 0.0
        # Log the real reply -- never the filler -- for debugging only; this
        # list is not sent to GuideAnts (continuation is by conversation id,
        # see module docstring).
        if reply_text:
            st.messages.append({"role": "assistant", "content": reply_text})
            logger.info("Agent said: %r", reply_text[:400])
            st.guide_awaiting_answer = reply_text.rstrip().endswith("?")
            # Cleared so a later barge-in cancellation (which lands during
            # the pacing sleep below, not during generation) doesn't re-append
            # this same content via the st.partial_reply check in the `prompt`
            # handler. The playback fields take over from here: they let that
            # same barge-in handler estimate how much of the reply the caller
            # actually heard before interrupting.
            st.partial_reply = ""
            st.playback_text = reply_text
            st.playback_start = asyncio.get_event_loop().time()
        # Every turn streams token-by-token, but Twilio still buffers/plays TTS
        # far slower than the deltas arrive -- this task would otherwise be
        # marked "done" well before Twilio actually finishes speaking the
        # reply aloud, making mid-reply caller speech look like it arrived
        # after the reply ended and incorrectly starting a brand-new turn.
        # Hold the task open until Twilio's agent-stopped speaker event says
        # playback actually finished (events="speaker-events", see
        # speaker_events.py); until the first such event has been recognized
        # this call, fall back to the estimated remaining speaking time,
        # exactly as before.
        spoken_text = f"{filler} {reply_text}" if filler else reply_text
        estimated_duration = speech_timing.estimate_seconds(spoken_text, config.TTS_WORDS_PER_SECOND)
        if st.agent_stop_seen:
            # Cleared only now so stale sets (the welcome greeting ending, or
            # the filler finishing while GuideAnts was still thinking) can't
            # release the wait early: the stop event that matters here can't
            # fire yet, since the reply was sent milliseconds ago and takes
            # seconds to play.
            st.playback_done.clear()
            # The estimate degrades to a generous ceiling, measured from now
            # (playback of the just-sent reply is only starting), so a lost
            # event can't hold the turn open forever.
            ceiling = estimated_duration * 1.5 + 2.0
            try:
                await asyncio.wait_for(st.playback_done.wait(), timeout=ceiling)
            except asyncio.TimeoutError:
                logger.warning(
                    "No agent-stopped speaker event within %.1fs; releasing turn on the estimate",
                    ceiling,
                )
        else:
            remaining = estimated_duration - (asyncio.get_event_loop().time() - start_time)
            if remaining > 0:
                await asyncio.sleep(remaining)
        if st.guide.end_call_requested and reply_text:
            await _end_call()
        elif st.guide.end_call_requested:
            # The guide hung up without saying anything (18:46 false start:
            # the caller heard silence) -- say the ready-made goodbye first.
            logger.info("endCall with no spoken goodbye; playing the ready-made goodbye first")
            await _canned_goodbye()
        elif reply_text and config.AUTO_END_CALL_ENABLED:
            # Backup when the guide said goodbye but didn't call endCall.
            assistants = [x["content"] for x in st.messages if x["role"] == "assistant"]
            users = [x["content"] for x in st.messages if x["role"] == "user"]
            previous_agent = assistants[-2] if len(assistants) >= 2 else ""
            if users and call_end.should_end(previous_agent, users[-1], reply_text):
                logger.info("Caller is done and reply was a goodbye; ending call (server-side backup)")
                await _end_call()

    async def _end_call() -> None:
        """Goodbye has finished playing: hand the call back to Twilio, which
        reaches the <Hangup/> after <Connect> and ends the call."""
        st.guide.end_call_requested = False
        await asyncio.sleep(config.END_CALL_AFTER_PLAYBACK_SECONDS)
        logger.info("Caller is done; ending ConversationRelay session (endCall)")
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {"type": "end", "handoffData": json.dumps({"reasonCode": "caller-done"})}
            )

    async def _canned_goodbye() -> None:
        """Speak the ready-made goodbye, wait for it to finish playing, then
        hang up the same way endCall does."""
        text = canned_goodbye_text()
        st.reply_first_frame_at = asyncio.get_event_loop().time()
        await websocket.send_json({"type": "text", "token": text, "last": True, "preemptible": True})
        st.messages.append({"role": "assistant", "content": text})
        estimated = speech_timing.estimate_seconds(text, config.TTS_WORDS_PER_SECOND)
        if st.agent_stop_seen:
            st.playback_done.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(st.playback_done.wait(), timeout=estimated * 1.5 + 2.0)
        else:
            await asyncio.sleep(estimated)
        await _end_call()

    def _wants_canned_goodbye(user_text: str) -> bool:
        if not config.CANNED_GOODBYE_ENABLED:
            return False
        assistants = [x["content"] for x in st.messages if x["role"] == "assistant"]
        last_agent = assistants[-1] if assistants else ""
        # Only right after "anything else?" -- anywhere else (mid-booking) the
        # model handles it. caller_done() also covers "bye"/"goodbye".
        return call_end.asked_anything_else(last_agent) and call_end.caller_done(user_text)

    def _one_word_name_reply() -> bool:
        """The agent just asked for the caller's name and all we have so far is
        one word -- likely a first name with the last name still coming."""
        if config.NAME_EXTRA_WAIT_SECONDS <= 0:
            return False
        words = (st.pending_text or "").split()
        if len(words) != 1:
            return False
        agent = [x["content"] for x in st.messages if x["role"] == "assistant"]
        last = (agent[-1] if agent else "").lower()
        return "name" in last and "spell" not in last and "?" in last

    def start_reply(user_text: str) -> None:
        _agent_lines = [x["content"] for x in st.messages if x["role"] == "assistant"]
        fixed = stt_fixups.fix_choice(_agent_lines[-1] if _agent_lines else "", user_text)
        if fixed != user_text:
            logger.info("Heard %r after 'text or email?'; treating it as %r", user_text, fixed)
            user_text = fixed
        if _wants_canned_goodbye(user_text):
            st.messages.append({"role": "user", "content": user_text})
            st.interrupted_reply = None
            st.partial_reply = ""
            st.playback_text = ""
            st.guide_awaiting_answer = False
            logger.info("Caller is done after 'anything else?'; ready-made goodbye, no model turn")
            st.task = asyncio.create_task(_canned_goodbye())
            return
        input_text = build_input(user_text, st.interrupted_reply)
        if st.interrupted_reply:
            logger.info("Folding interruption note into next turn: %r", input_text)
        st.interrupted_reply = None
        st.messages.append({"role": "user", "content": user_text})
        st.partial_reply = ""
        st.playback_text = ""
        st.guide_awaiting_answer = False
        st.tool_call_started_at = 0.0
        st.task = asyncio.create_task(respond_to(input_text, fillers.looks_like_question(user_text)))

    def _arm_commit(delay: float) -> None:
        if delay < PENDING_TURN_CEILING_SECONDS and _one_word_name_reply():
            delay += config.NAME_EXTRA_WAIT_SECONDS
        if st.pending_commit and not st.pending_commit.done():
            st.pending_commit.cancel()
        st.pending_commit = asyncio.create_task(_commit_pending_after(delay))

    async def _commit_pending_after(delay: float) -> None:
        await asyncio.sleep(delay)
        # No awaits from here on, so a commit that has passed the sleep can't
        # interleave with the WS loop: the text is taken and the reply started
        # atomically. (A re-armed timer that fires after this finds
        # pending_text empty and does nothing.)
        text, st.pending_text = st.pending_text, ""
        if not text:
            return
        if st.client_speaking:
            logger.warning(
                "Committing buffered turn while caller still speaking (%.0fs ceiling hit): %r",
                delay,
                text,
            )
        else:
            logger.info("Caller stayed quiet %.1fs; committing turn: %r", delay, text)
        start_reply(text)

    def schedule_turn(user_text: str) -> None:
        # Twilio finalizes a prompt at each pause in caller speech, so this
        # transcript may only be the first half of the caller's turn. Buffer
        # it and commit only after TURN_PAUSE_SECONDS of further silence; if
        # the caller is already speaking again by the time it lands (they
        # resumed before STT finished finalizing), hold the buffer instead --
        # the coming clientSpeaking-stop event re-arms the real window.
        st.pending_text = f"{st.pending_text} {user_text}".strip()
        _arm_commit(
            PENDING_TURN_CEILING_SECONDS if st.client_speaking else config.TURN_PAUSE_SECONDS
        )

    async def _cancel_and_await(task) -> None:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def cancel_task() -> None:
        t, st.task = st.task, None
        await _cancel_and_await(t)

    authenticated = False

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON WS frame: %r", raw)
                continue

            msg_type = msg.get("type")

            if msg_type == "setup":
                call_sid = msg.get("callSid", "")
                if not twilio_auth.verify_ws_token(token, call_sid):
                    logger.warning("Rejecting /ws: invalid token for callSid=%s", call_sid)
                    await websocket.close(code=1008)  # policy violation
                    return

                authenticated = True
                st.guide.caller_phone = msg.get("from")
                if config.FAST_TOOLS_ENABLED and config.BOOQABLE_API_KEY and st.guide.prefetch_task is None:
                    st.guide.prefetch_task = asyncio.create_task(guide_client.prefetch_booqable(st.guide))
                if config.KNOWN_CALLER_NOTE_ENABLED and config.BOOQABLE_API_KEY and st.guide.caller_lookup_task is None:
                    st.guide.caller_lookup_task = asyncio.create_task(guide_client.lookup_known_caller(st.guide))
                logger.info(
                    "Call setup: callSid=%s from=%s to=%s",
                    msg.get("callSid"),
                    mask_phone(msg.get("from")),
                    mask_phone(msg.get("to")),
                )

            elif not authenticated:
                # No branch below this may touch the guide or any
                # tool-calling code until a valid `setup` has verified the
                # token -- otherwise a client could skip `setup` entirely
                # and drive the guide (including reservation/payment tools)
                # with zero authentication. Reject exactly like a failed
                # setup does.
                logger.warning(
                    "Rejecting /ws: message type %r before authenticated setup", msg_type
                )
                await websocket.close(code=1008)  # policy violation
                return

            elif msg_type == "prompt":
                text = msg.get("voicePrompt", "") or ""
                if text.strip():
                    if st.task and not st.task.done():
                        # A client-side tool call may have left the guide
                        # quiet mid-turn (real tool latency, not a finished
                        # reply) -- soften barge-in for that gap so a
                        # rephrase/"hello?" doesn't cancel the answer that's
                        # still coming. An explicit stop/wait phrase always
                        # still cuts through immediately.
                        tool_pending = bool(st.tool_call_started_at) and (
                            asyncio.get_event_loop().time() - st.tool_call_started_at
                            < config.TOOL_CALL_BARGE_IN_GRACE_SECONDS
                        )
                        if tool_pending and not barge_in.is_stop_command(text, config.EXTRA_STOP_PHRASES):
                            logger.info(
                                "Ignoring caller speech while a tool result is pending: %r", text
                            )
                        elif barge_in.should_interrupt(text, config.EXTRA_STOP_PHRASES):
                            await cancel_task()
                            # Remember what the caller actually heard as
                            # st.interrupted_reply, so the *next* real question
                            # (whether this one, if it's a new question, or a
                            # later one after a stop command) can tell the
                            # guide about the cut-off. Two cases:
                            #
                            # Mid-generation: st.partial_reply holds the real
                            # reply text streamed so far (never the filler) --
                            # log it too, same as a normal completed turn.
                            if st.partial_reply:
                                st.messages.append({"role": "assistant", "content": st.partial_reply})
                                st.interrupted_reply = st.partial_reply
                                st.partial_reply = ""
                            # Mid-playback (the common case when the model
                            # returns the whole reply in one burst): the full
                            # reply was already logged and partial_reply
                            # cleared, but Twilio was still speaking it aloud.
                            # Estimate how far playback had gotten from the
                            # elapsed time at the configured speaking rate;
                            # no note if it hadn't plausibly started, or had
                            # already finished, being heard.
                            elif st.playback_text:
                                elapsed = asyncio.get_event_loop().time() - st.playback_start
                                heard = speech_timing.estimate_spoken_prefix(
                                    st.playback_text, elapsed, config.TTS_WORDS_PER_SECOND
                                )
                                if heard and heard != st.playback_text:
                                    st.interrupted_reply = heard
                                st.playback_text = ""
                            if barge_in.is_stop_command(text, config.EXTRA_STOP_PHRASES):
                                # Stop/wait means stop -- acknowledge locally
                                # and go silent rather than asking GuideAnts
                                # what to say next, which would both add a
                                # round-trip before playback cuts over and
                                # leave whether the turn actually ends up to
                                # the guide's own reply. Never sent through
                                # GuideAnts, so (like fillers) never recorded
                                # in st.messages either.
                                logger.info("Stop command heard during active reply -- cancelling and going silent: %r", text)
                                ack = fillers.pick(config.STOP_ACK_PHRASES)
                                if ack:
                                    await websocket.send_json(
                                        {"type": "text", "token": ack, "last": True, "preemptible": True}
                                    )
                            else:
                                logger.info("Interrupting active reply for a new question: %r", text)
                                schedule_turn(text)
                        else:
                            # Logged only, never sent to GuideAnts or added to
                            # st.messages -- this utterance wasn't a trigger,
                            # so it's treated as noise, not a real turn.
                            logger.info("Ignored caller speech during active reply (not acted on): %r", text)
                    elif st.pending_text:
                        # A turn is already buffered awaiting the pause
                        # window, so this is the caller continuing that same
                        # turn -- merge it, even if this fragment alone would
                        # look like a backchannel ("...yeah" mid-sentence).
                        schedule_turn(text)
                    elif st.guide_awaiting_answer:
                        # The guide's last reply ended in a question it's
                        # waiting on the caller to answer, so a short
                        # affirmative here ("yeah", "yep", ...) is the
                        # answer, not backchannel noise -- skip the
                        # is_backchannel() check below and treat it as a
                        # real turn.
                        schedule_turn(text)
                    elif (
                        config.IGNORE_FIRST_BARE_GREETING
                        and not st.bare_greeting_ignored
                        and not any(m["role"] == "user" for m in st.messages)
                        and call_end.is_bare_greeting(text)
                    ):
                        # The welcome greeting already asked how to help; a
                        # lone "hi" is the caller (or line noise) starting --
                        # wait for the actual request instead of greeting again.
                        st.bare_greeting_ignored = True
                        logger.info("Ignored bare first-turn greeting (waiting for more speech): %r", text)
                    elif fillers.is_backchannel(text, config.EXTRA_BACKCHANNEL_PHRASES):
                        # STT can finish transcribing a short "ok" after the
                        # reply has already finished playing, so this branch
                        # (not just the one above) also has to swallow pure
                        # acknowledgments -- otherwise a late "ok" looks like
                        # a brand-new prompt and gets its own guide reply.
                        # Never sent to GuideAnts or logged to st.messages,
                        # for the same reason as above.
                        logger.info("Ignored backchannel utterance (not acted on): %r", text)
                    else:
                        schedule_turn(text)

            elif msg_type == "interrupt":
                logger.info("Received interrupt message (unexpected with interruptible=none): %s", msg.get("utteranceUntilInterrupt"))

            elif msg_type == "dtmf":
                logger.info("DTMF digit: %s", msg.get("digit"))

            elif msg_type == "error":
                logger.error("Conversation Relay error: %s", msg.get("description"))

            # Only unhandled types reach the classifier, so a prompt whose
            # transcript happens to mention "agent speaking" can't match.
            elif msg_type == "info" and msg.get("name") == "mediaPlaying":
                if msg.get("value") == "on" and st.reply_text_after_play:
                    # The chime only started after the reply had begun (Twilio
                    # fetched it late and queued it behind the reply): cut it.
                    logger.info("Working sound started after the reply; cutting it")
                    with contextlib.suppress(Exception):
                        await websocket.send_json(
                            {"type": "text", "token": " ", "last": True, "preemptible": True}
                        )
                    st.reply_text_after_play = False
                elif msg.get("value") == "off":
                    st.working_play_sent = False
                    st.reply_text_after_play = False

            elif (speaker_kind := speaker_events.classify(msg)) is not None:
                if speaker_kind == "agent-stop":
                    st.agent_stop_seen = True
                    st.playback_done.set()
                elif speaker_kind == "agent-start" and not st.reply_first_frame_at:
                    st.last_agent_start_at = asyncio.get_event_loop().time()
                elif speaker_kind == "agent-start" and st.reply_first_frame_at:
                    st.last_agent_start_at = asyncio.get_event_loop().time()
                    # Closest thing to a receipt Twilio gives back for a
                    # reply's text frames: not an ack of receiving them, but
                    # confirmation it has started speaking them, which it
                    # can't do without having received (and TTS'd) them
                    # first. Compare against respond_to()'s "last frame
                    # sent" TIMING log to see the app -> Twilio gap in full.
                    now = asyncio.get_event_loop().time()
                    logger.info(
                        "TIMING: first frame sent to Twilio -> Twilio agent-start (playback begins): %.3fs",
                        now - st.reply_first_frame_at,
                    )
                    if st.client_stop_at and st.client_stop_at < st.reply_first_frame_at:
                        logger.info(
                            "TIMING: caller stopped speaking -> agent playback begins: %.3fs",
                            now - st.client_stop_at,
                        )
                    st.reply_first_frame_at = 0.0
                elif speaker_kind == "client-start":
                    st.client_speaking = True
                    # The caller resumed while a turn was buffered: hold the
                    # buffer for their continuation instead of committing a
                    # half-finished turn. The ceiling applies only while
                    # they're audibly speaking -- the coming stop event
                    # re-arms the real window below.
                    if st.pending_text:
                        _arm_commit(PENDING_TURN_CEILING_SECONDS)
                elif speaker_kind == "client-stop":
                    st.client_stop_at = asyncio.get_event_loop().time()
                    st.client_speaking = False
                    # The continuation's transcript trails this event by STT
                    # finalization time, so give it TURN_RESUME_GRACE_SECONDS
                    # (longer than the plain pause window) to arrive before
                    # committing what we have. A stop with nothing buffered
                    # is just the normal end of an utterance whose prompt
                    # hasn't arrived yet -- nothing to re-arm.
                    if st.pending_text:
                        _arm_commit(config.TURN_RESUME_GRACE_SECONDS)
                # Full payload logged on purpose: Twilio doesn't document
                # these messages' shape, so the log is how a mismatch with
                # speaker_events.classify gets noticed and fixed.
                logger.info("Speaker event %s: %s", speaker_kind, msg)

            else:
                logger.warning("Unhandled message type: %s (%s)", msg_type, msg)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    finally:
        # Pending-turn timer first: were it still alive, it could fire during
        # the await below and start_reply() a brand-new task that cancel_task()
        # already missed.
        timer, st.pending_commit = st.pending_commit, None
        await _cancel_and_await(timer)
        await cancel_task()
        if authenticated:
            try:
                await call_recording.record_call(st)
            except Exception:
                logger.exception("Failed to persist conversation record")
