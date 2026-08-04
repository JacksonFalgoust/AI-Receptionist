#!/usr/bin/env python3
"""Local logging reverse-proxy for this app -> GuideAnts (debug tool).

check_streaming.py measures request/first-token/last-token timing by
driving guide_client.stream_reply() directly with canned prompts, offline.
This script gets the same TIMING numbers for REAL traffic during a live
Twilio call, without touching app code or restarting anything mid-call:
point this app's GUIDEANTS_BASE_URL at the proxy, and every request
app/guide_client.py sends to GuideAnts is forwarded through here to the
real GuideAnts host, with timing logged as the response streams back.

Unlike check_streaming.py -- which only ever sees the final, already-
buffered round, because _stream_reply_with_tools discards narration ahead
of a tool call before anything reaches Twilio (see app/guide_client.py) --
this proxy sits below that buffering, at the network level: it logs ONE
request/response cycle per responses.create() call GuideAnts receives, so
a turn that needs a tool call shows up as two or more separate entries
here, including the intermediate round(s) the app throws away. That makes
this the right tool for seeing what GuideAnts itself is doing during a
live call (e.g. is the narration-ahead-of-a-tool-call round even fast, or
is most of the latency in the round after the tool result goes back);
check_streaming.py is still the right tool for what finally reaches
Twilio.

USAGE
    python scripts/check_streaming_proxy.py                # listens on 127.0.0.1:8899
    python scripts/check_streaming_proxy.py --port 9001
    python scripts/check_streaming_proxy.py --upstream http://localhost:5107

Then, in .env, point this app at the proxy instead of the real GuideAnts
host:
    GUIDEANTS_BASE_URL=http://localhost:8899
and restart the app (not the proxy) so it picks up the new value. Make a
call, and watch this terminal for TIMING/RESULT lines per round.

REVERT .env's GUIDEANTS_BASE_URL back to the real GuideAnts host when done
-- this proxy adds latency and is not meant to run in production.

Default --upstream is read from app/config.py's GUIDEANTS_BASE_URL, i.e.
whatever GUIDEANTS_BASE_URL resolves to right now. Read that BEFORE you
edit .env to point at the proxy (start this proxy first) -- otherwise
you'll capture the proxy's own address as "upstream" and create a loop.
The self-loop guard below catches the case where the two happen to match.

Captures are written to scripts/captures/ (git-ignored). No third-party
packages required beyond what this repo already depends on (python-dotenv,
for reading .env via app/config.py's default).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import http.client
import json
import os
import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

# Headers we must not copy verbatim when relaying (connection-scoped, or ones
# we set ourselves). Accept-Encoding is dropped so upstream returns plain
# text we can log/reassemble instead of gzip.
_HOP_BY_HOP = {
    "host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length", "accept-encoding",
}

# Keep in sync with scripts/check_streaming.py's constant of the same name --
# below this, multiple token events are still reported as one burst rather
# than genuinely incremental streaming.
_INCREMENTAL_SPAN_THRESHOLD_SECONDS = 0.05

_counter_lock = threading.Lock()
_counter = 0


def _next_index() -> int:
    global _counter
    with _counter_lock:
        _counter += 1
        return _counter


def _ts() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _ensure_capture_dir() -> None:
    os.makedirs(CAPTURE_DIR, exist_ok=True)


def _default_upstream() -> str:
    """Best-effort default upstream: app/config.py's current
    GUIDEANTS_BASE_URL (see module docstring for the ordering caveat).
    Falls back to GuideAnts' own out-of-the-box default if the app package
    can't be imported (e.g. this script copied out of the repo)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app import config as _config
        return _config.GUIDEANTS_BASE_URL
    except Exception:
        return "http://localhost:5107"


def _summarize_request(body: bytes) -> str:
    try:
        obj = json.loads(body)
    except Exception:
        return f"(non-JSON body, {len(body)} bytes)"
    model = obj.get("model")
    stream = obj.get("stream")
    conv = obj.get("conversation")
    inp = obj.get("input")
    if isinstance(inp, str):
        input_desc = f"input=str({len(inp)}c)"
    elif isinstance(inp, list):
        kinds = [item.get("type", "?") for item in inp if isinstance(item, dict)]
        input_desc = f"input=list({kinds})"
    else:
        input_desc = f"input={inp!r}"
    return f"model={model}  stream={stream}  conversation={conv!r}  {input_desc}"


def _sse_event_type(raw_event: bytes) -> str | None:
    """First `data:` line's `type` field within one blank-line-delimited SSE
    event block, or None if it isn't a data event we can parse."""
    for line in raw_event.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            evt = json.loads(data)
        except Exception:
            continue
        return evt.get("type")
    return None


def _reassemble_responses_sse(raw: bytes) -> dict:
    """Rebuild the assistant turn from a GuideAnts /v1/responses SSE stream,
    matching the event types app/guide_client.py's _stream_turn understands,
    for the post-completion summary line."""
    content = []
    function_calls: list[str] = []
    conversation_id = None
    completed = False
    for block in raw.replace(b"\r\n", b"\n").split(b"\n\n"):
        if not block.strip():
            continue
        for line in block.decode("utf-8", "replace").splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                evt = json.loads(data)
            except Exception:
                continue
            etype = evt.get("type")
            if etype == "response.output_text.delta":
                content.append(evt.get("delta") or "")
            elif etype == "response.output_item.done":
                item = evt.get("item") or {}
                if item.get("type") == "function_call" and item.get("name"):
                    function_calls.append(item["name"])
            elif etype in ("response.created", "response.completed"):
                resp = evt.get("response") or {}
                conv = resp.get("conversation")
                if isinstance(conv, str) and conv:
                    conversation_id = conv
                elif isinstance(conv, dict) and conv.get("id"):
                    conversation_id = conv["id"]
                if etype == "response.completed":
                    completed = True
    return {
        "content": "".join(content),
        "function_calls": function_calls,
        "conversation_id": conversation_id,
        "completed": completed,
    }


def _make_handler(upstream_scheme: str, upstream_host: str, upstream_port: int):
    class _Proxy(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # noqa: N802 -- quieter default logging
            return

        def do_GET(self):  # noqa: N802
            self._relay()

        def do_POST(self):  # noqa: N802
            self._relay()

        def _relay(self) -> None:
            idx = _next_index()
            ts = _ts()
            t_request_received = time.monotonic()
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            is_responses = "/responses" in self.path

            if is_responses:
                _ensure_capture_dir()
                req_path = os.path.join(CAPTURE_DIR, f"ga_{ts}_{idx:04d}_request.json")
                with open(req_path, "wb") as fh:
                    fh.write(_pretty(body))
                print(f"\n[{idx}] --> {self.command} {self.path}")
                print(f"      {_summarize_request(body)}")
            else:
                print(f"\n[{idx}] --> {self.command} {self.path}  (non-/responses, forwarding only)")

            fwd_headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP_BY_HOP}
            fwd_headers["Host"] = upstream_host
            fwd_headers["Accept-Encoding"] = "identity"

            conn_cls = http.client.HTTPSConnection if upstream_scheme == "https" else http.client.HTTPConnection
            conn_kwargs = {"timeout": 120}
            if upstream_scheme == "https":
                conn_kwargs["context"] = ssl.create_default_context()

            try:
                conn = conn_cls(upstream_host, upstream_port, **conn_kwargs)
                conn.request(self.command, self.path, body=body, headers=fwd_headers)
                resp = conn.getresponse()
            except Exception as exc:  # upstream unreachable, connection refused, etc.
                self.send_error(502, f"Proxy upstream error: {exc}")
                print(f"[{idx}] !! upstream error: {exc}")
                return

            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in _HOP_BY_HOP or k.lower() == "content-length":
                    continue
                self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            captured = bytearray()
            pending = bytearray()  # undelimited tail, carried across chunk reads
            t_first_byte = None
            t_first_token = None
            t_last_token = None
            read1 = getattr(resp, "read1", None)
            try:
                while True:
                    chunk = read1(65536) if read1 else resp.read(65536)
                    if not chunk:
                        break
                    now = time.monotonic()
                    if t_first_byte is None:
                        t_first_byte = now
                    captured.extend(chunk)
                    # Attribute each *complete* SSE event (not raw chunk) to
                    # this read's arrival time, so an event split across two
                    # TCP reads is still classified correctly -- a chunk
                    # boundary rarely lines up with an SSE blank-line
                    # boundary, but the (possibly late-by-one-read)
                    # timestamp this yields is close enough for this
                    # diagnostic's purpose.
                    pending.extend(chunk)
                    while b"\n\n" in pending:
                        raw_event, _, rest = pending.partition(b"\n\n")
                        pending = bytearray(rest)
                        if _sse_event_type(bytes(raw_event)) == "response.output_text.delta":
                            if t_first_token is None:
                                t_first_token = now
                            t_last_token = now
                    self.wfile.write(b"%X\r\n" % len(chunk) + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                # The app closed the connection mid-stream, e.g. a barge-in
                # aclose() cancelling the in-flight turn.
                print(f"[{idx}] .. app closed connection mid-stream")
            finally:
                conn.close()

            t_done = time.monotonic()
            self._report(
                idx, t_request_received, t_first_byte, t_first_token, t_last_token,
                t_done, resp, bytes(captured), is_responses, ts,
            )

        def _report(
            self, idx, t_request_received, t_first_byte, t_first_token, t_last_token,
            t_done, resp, raw: bytes, is_responses: bool, ts: str,
        ) -> None:
            if not is_responses:
                print(f"[{idx}] <-- {resp.status} ({len(raw)} bytes)")
                return

            raw_path = os.path.join(CAPTURE_DIR, f"ga_{ts}_{idx:04d}_response.txt")
            with open(raw_path, "wb") as fh:
                fh.write(raw)

            print(f"[{idx}] <-- {resp.status}  total={t_done - t_request_received:.3f}s")
            if t_first_token is None:
                print(f"[{idx}]     no response.output_text.delta events seen "
                      f"(tool-call-only round, or non-streaming/error response)")
            else:
                print(f"[{idx}]     TIMING: request sent -> first token received by app: {t_first_token - t_request_received:.3f}s")
                print(f"[{idx}]     TIMING: request sent -> last token received by app:  {t_last_token - t_request_received:.3f}s")
                span = t_last_token - t_first_token
                if span < _INCREMENTAL_SPAN_THRESHOLD_SECONDS:
                    print(f"[{idx}]     RESULT: tokens arrived within {span:.3f}s of each other -- one burst (buffered upstream).")
                else:
                    print(f"[{idx}]     RESULT: tokens spread over {span:.3f}s -- incremental streaming from GuideAnts.")

            summary = _reassemble_responses_sse(raw)
            reask_path = os.path.join(CAPTURE_DIR, f"ga_{ts}_{idx:04d}_response_reassembled.json")
            with open(reask_path, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=2, ensure_ascii=False)
            tool_note = f"  tool_calls={summary['function_calls']}" if summary["function_calls"] else ""
            print(f"[{idx}]     content={len(summary['content'])}c  completed={summary['completed']}"
                  f"  conversation={summary['conversation_id']!r}{tool_note}")
            print(f"      saved: {os.path.relpath(raw_path)}")

    return _Proxy


def _pretty(body: bytes) -> bytes:
    try:
        return json.dumps(json.loads(body), indent=2, ensure_ascii=False).encode("utf-8")
    except Exception:
        return body


def main() -> int:
    # stdout is block-buffered whenever it isn't an interactive terminal
    # (redirected to a file, piped, run as a background task) -- without
    # this, TIMING/RESULT lines for a live call can sit invisible in the
    # buffer for a long time (or until the process exits) instead of
    # appearing as the call happens, defeating the point of a live proxy.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass  # Python <3.7, or a stdout that doesn't support reconfigure

    ap = argparse.ArgumentParser(description="Local logging reverse-proxy for this app -> GuideAnts.")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--upstream", default=None, help="Real GuideAnts base URL, e.g. http://localhost:5107 (default: app/config.py's current GUIDEANTS_BASE_URL)")
    args = ap.parse_args()

    upstream = (args.upstream or _default_upstream()).rstrip("/")
    parsed = urlsplit(upstream)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        print(f"Bad --upstream URL: {upstream!r} (need e.g. http://localhost:5107)", file=sys.stderr)
        return 1
    upstream_scheme = parsed.scheme
    upstream_host = parsed.hostname
    upstream_port = parsed.port or (443 if upstream_scheme == "https" else 80)

    proxy_host_for_compare = "localhost" if args.host in ("0.0.0.0", "::") else args.host
    if upstream_host in (proxy_host_for_compare, "127.0.0.1", "localhost") and upstream_port == args.port:
        print(
            f"Refusing to start: --upstream ({upstream}) points at this proxy's own "
            f"address ({args.host}:{args.port}) -- that's a self-loop, most likely "
            f"because .env's GUIDEANTS_BASE_URL was already pointed at the proxy "
            f"before this default was read. Pass --upstream explicitly with the "
            f"real GuideAnts base URL.",
            file=sys.stderr,
        )
        return 1

    _ensure_capture_dir()
    listening_all = args.host in ("0.0.0.0", "::")
    proxy_url = f"http://{'localhost' if listening_all else args.host}:{args.port}"
    print("=" * 72)
    print("  This app -> GuideAnts logging proxy")
    print("=" * 72)
    print(f"  Listening on   http://{args.host}:{args.port}")
    print(f"  Forwarding to  {upstream_scheme}://{upstream_host}:{upstream_port}")
    print(f"  Captures in    {CAPTURE_DIR}")
    print()
    print("  1) In .env, set:")
    print(f"         GUIDEANTS_BASE_URL={proxy_url}")
    if listening_all:
        print("     (App in Docker -> use host.docker.internal instead of localhost)")
    print("     Restart the app (not this proxy) so it picks up the new value.")
    print("  2) Make a call.")
    print("  3) Read the TIMING/RESULT lines below as each round streams back.")
    print("  4) REVERT GUIDEANTS_BASE_URL to the real GuideAnts host when done.")
    print("=" * 72, flush=True)

    handler = _make_handler(upstream_scheme, upstream_host, upstream_port)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
