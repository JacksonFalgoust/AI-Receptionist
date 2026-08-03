#!/usr/bin/env python3
"""Local logging reverse-proxy for GuideAnts -> OpenRouter (debug tool).

Point GuideAnts' OpenRouter Base URL at this proxy and it forwards every call
to https://openrouter.ai, streaming the response straight through while
capturing the exact request and response to disk. Use it to see precisely what
GuideAnts sends OpenRouter for the DeepSeek V4 Flash guide -- e.g. whether any
`reasoning` / `reasoning_effort` field is present, and whether the model's
thinking comes back inline in `content` (`<think>...`) or in a separate
`reasoning` field (which GuideAnts' OpenRouter client drops).

USAGE
    python scripts/openrouter_proxy.py            # listens on 127.0.0.1:8888
    python scripts/openrouter_proxy.py --port 9000

Then set GuideAnts' OpenRouter Base URL to:
    http://localhost:8888/api/v1
(Settings -> Models & Runtime -> OpenRouter provider config, or env
 OpenRouter__BaseUrl). GuideAnts posts to {BaseUrl}/chat/completions, so the
incoming path /api/v1/chat/completions is forwarded to
https://openrouter.ai/api/v1/chat/completions. Your Bearer key passes straight
through -- this proxy never reads or stores it.

REVERT the Base URL back to https://openrouter.ai/api/v1 when you're done.

Captures are written to scripts/captures/ (git-ignore it). No third-party
packages required -- Python 3.8+ stdlib only.
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM_HOST = "openrouter.ai"
CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

# Headers we must not copy verbatim when relaying (connection-scoped, or ones we
# set ourselves). Accept-Encoding is dropped so upstream returns plain text we
# can log/reassemble instead of gzip.
_HOP_BY_HOP = {
    "host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length", "accept-encoding",
}

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


def _summarize_request(body: bytes) -> str:
    try:
        obj = json.loads(body)
    except Exception:
        return f"(non-JSON body, {len(body)} bytes)"
    model = obj.get("model")
    stream = obj.get("stream")
    messages = obj.get("messages") or []
    tools = obj.get("tools") or []
    bits = [f"model={model}", f"stream={stream}", f"messages={len(messages)}", f"tools={len(tools)}"]
    # The whole point: is any reasoning-control field being sent?
    for key in ("reasoning", "reasoning_effort", "provider", "chat_template_kwargs"):
        if key in obj:
            bits.append(f"{key}={json.dumps(obj[key])}")
    if "reasoning" not in obj and "reasoning_effort" not in obj:
        bits.append("reasoning=<none sent>")
    return "  ".join(bits)


def _reassemble_sse(raw: bytes) -> dict:
    """Rebuild the assistant turn from an OpenAI-style SSE stream so we can see
    where the model's thinking went. Returns accumulated content/reasoning and
    a couple of derived flags."""
    content, reasoning = [], []
    tool_call_ids = set()
    finish = None
    for line in raw.decode("utf-8", "replace").splitlines():
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
        for choice in evt.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                content.append(delta["content"])
            # OpenRouter normalizes DeepSeek thinking into `reasoning`; some
            # providers use `reasoning_content`. GuideAnts' OpenRouter client
            # reads neither -- so if thinking shows up ONLY here, it is dropped.
            if delta.get("reasoning"):
                reasoning.append(delta["reasoning"])
            if delta.get("reasoning_content"):
                reasoning.append(delta["reasoning_content"])
            for tc in delta.get("tool_calls") or []:
                # Streaming tool-call arguments arrive as many fragments sharing
                # one index/id; count distinct calls, not fragments.
                tool_call_ids.add(tc.get("index", tc.get("id")))
            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
    joined_content = "".join(content)
    return {
        "content": joined_content,
        "reasoning": "".join(reasoning),
        "tool_calls": len(tool_call_ids),
        "finish_reason": finish,
        "reasoning_in_separate_field": bool(reasoning),
        "think_tags_inline_in_content": "<think>" in joined_content.lower(),
    }


def _parse_nonstream(raw: bytes) -> dict:
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    try:
        msg = obj["choices"][0]["message"]
    except Exception:
        return {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
    return {
        "content": content,
        "reasoning": reasoning,
        "tool_calls": len(msg.get("tool_calls") or []),
        "finish_reason": (obj["choices"][0].get("finish_reason")),
        "reasoning_in_separate_field": bool(reasoning),
        "think_tags_inline_in_content": "<think>" in str(content).lower(),
    }


class _Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Quieter default logging; we print our own summaries.
    def log_message(self, fmt, *args):  # noqa: N802
        return

    def do_GET(self):  # noqa: N802
        self._relay()

    def do_POST(self):  # noqa: N802
        self._relay()

    def _relay(self) -> None:
        idx = _next_index()
        ts = _ts()
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        is_chat = "/chat/completions" in self.path

        if is_chat:
            _ensure_capture_dir()
            req_path = os.path.join(CAPTURE_DIR, f"{ts}_{idx:04d}_request.json")
            with open(req_path, "wb") as fh:
                fh.write(_pretty(body))
            print(f"\n[{idx}] --> {self.command} {self.path}")
            print(f"      {_summarize_request(body)}")
            print(f"      saved: {os.path.relpath(req_path)}")

        # Forward upstream, streaming the response back as it arrives.
        fwd_headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP_BY_HOP}
        fwd_headers["Host"] = UPSTREAM_HOST
        fwd_headers["Accept-Encoding"] = "identity"

        try:
            conn = http.client.HTTPSConnection(
                UPSTREAM_HOST, 443, timeout=180, context=ssl.create_default_context()
            )
            conn.request(self.command, self.path, body=body, headers=fwd_headers)
            resp = conn.getresponse()
        except Exception as exc:  # upstream unreachable, TLS error, etc.
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
        read1 = getattr(resp, "read1", None)
        try:
            while True:
                chunk = read1(65536) if read1 else resp.read(65536)
                if not chunk:
                    break
                captured.extend(chunk)
                self.wfile.write(b"%X\r\n" % len(chunk) + chunk + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client (GuideAnts) went away mid-stream, e.g. a barge-in aclose().
            print(f"[{idx}] .. client closed mid-stream")
        finally:
            conn.close()

        if is_chat:
            self._report_response(idx, ts, resp, bytes(captured))

    def _report_response(self, idx: int, ts: str, resp, raw: bytes) -> None:
        raw_path = os.path.join(CAPTURE_DIR, f"{ts}_{idx:04d}_response.txt")
        with open(raw_path, "wb") as fh:
            fh.write(raw)

        ctype = resp.getheader("Content-Type", "")
        summary = _reassemble_sse(raw) if "event-stream" in ctype or raw.lstrip().startswith(b"data:") else _parse_nonstream(raw)
        if summary:
            reask = os.path.join(CAPTURE_DIR, f"{ts}_{idx:04d}_response_reassembled.json")
            with open(reask, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=2, ensure_ascii=False)
            leak = (
                "INLINE <think> in content (LEAKS)" if summary.get("think_tags_inline_in_content")
                else ("separate `reasoning` field (dropped by GuideAnts)" if summary.get("reasoning_in_separate_field")
                      else "no reasoning surfaced")
            )
            print(f"[{idx}] <-- {resp.status}  finish={summary.get('finish_reason')}  "
                  f"content={len(summary.get('content',''))}c  reasoning={len(summary.get('reasoning',''))}c  "
                  f"tool_calls={summary.get('tool_calls')}")
            print(f"      thinking: {leak}")
            print(f"      saved: {os.path.relpath(raw_path)}")
        else:
            print(f"[{idx}] <-- {resp.status} (saved raw: {os.path.relpath(raw_path)})")


def _pretty(body: bytes) -> bytes:
    try:
        return json.dumps(json.loads(body), indent=2, ensure_ascii=False).encode("utf-8")
    except Exception:
        return body


def main() -> int:
    ap = argparse.ArgumentParser(description="Local logging reverse-proxy for GuideAnts -> OpenRouter.")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    _ensure_capture_dir()
    listening_all = args.host in ("0.0.0.0", "::")
    if listening_all:
        base_url = f"http://host.docker.internal:{args.port}/api/v1"
        base_hint = "GuideAnts in Docker -> use host.docker.internal (NOT localhost)"
    else:
        base_url = f"http://localhost:{args.port}/api/v1"
        base_hint = "GuideAnts as a native process on this host"
    print("=" * 72)
    print("  GuideAnts -> OpenRouter logging proxy")
    print("=" * 72)
    print(f"  Listening on   http://{args.host}:{args.port}")
    print(f"  Forwarding to  https://{UPSTREAM_HOST}")
    print(f"  Captures in    {CAPTURE_DIR}")
    print()
    print("  1) Set GuideAnts OpenRouter Base URL to:")
    print(f"         {base_url}")
    print(f"     ({base_hint})")
    print("     Settings -> Models & Runtime -> OpenRouter, or env OpenRouter__BaseUrl")
    if not listening_all:
        print("     If GuideAnts runs in Docker, localhost won't reach this proxy --")
        print("     stop this, then restart bound to all interfaces:")
        print(f"         python scripts/openrouter_proxy.py --host 0.0.0.0 --port {args.port}")
        print(f"     and use  http://host.docker.internal:{args.port}/api/v1")
    print("  2) Make a call through the DeepSeek V4 Flash guide.")
    print("  3) Read the summaries below / the captures/ files.")
    print("  4) REVERT Base URL to https://openrouter.ai/api/v1 when done.")
    print("=" * 72, flush=True)

    server = ThreadingHTTPServer((args.host, args.port), _Proxy)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
