"""Measures one branch's guide_client.stream_reply behavior against a live
GuideAnts guide -- the same function app/main.py's respond_to() calls, so
the numbers reported are what would actually reach Twilio on that branch.

Meant to be pointed at a git worktree checked out to a specific branch (see
scripts/compare_branches.py, which drives this across main,
feature/live-token-streaming, and feature/trigger-phrase and aggregates the
results). Usable standalone too:

    python scripts/compare_streaming.py --repo <worktree_dir> --label main --reps 3 --out results.json

`--repo` is inserted at sys.path[0] and os.chdir()'d into *before* `app` is
imported, so this process picks up that worktree's own code -- not
whatever's on this repo's current branch -- and its own `.env`
(app/config.py's `load_dotenv()` reads from the current working directory).
This is why this script takes `--repo` rather than the fixed
`Path(__file__).parent.parent` trick scripts/check_streaming.py uses: that
trick would always resolve to this file's own checkout, not the worktree
under test.

Three branches export different event shapes from stream_reply:
  - main:                                yields `str` only (no tool-call marker)
  - feature/live-token-streaming:        yields `Delta`/`ToolCallStarted` dataclasses
  - feature/trigger-phrase:              yields the same `Delta`/`ToolCallStarted` shape
Rather than import each branch's dataclasses (which would require this
script itself to be checked out identically on all three, defeating the
point), events are duck-typed: a `ToolCallStarted`-shaped event is anything
whose class is literally named that; everything else is treated as spoken
text, read from `.text` if present (the dataclass shape) or the value
itself (a plain `str`, as `main` yields).

Not part of the app -- safe to delete once the three-way comparison is done.
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

# Fixed 3-turn script driven against every branch, so the comparison holds
# the caller's side of the conversation constant. Turn 2 exercises a single
# client-side tool call (listCatalog); turn 3 exercises a multi-tool round
# (checkAvailability for both a bike and a helmet) -- the two shapes each
# branch's anti-narration mechanism has to get right.
_TURNS = [
    ("no_tool", "What are your hours?"),
    ("one_tool", "What bikes do you have to rent?"),
    ("multi_tool", "Is the cruiser available Saturday from ten to two, and do you have a helmet?"),
]


def _is_tool_call_event(ev) -> bool:
    return type(ev).__name__ == "ToolCallStarted"


def _tool_call_names(ev) -> tuple:
    return tuple(getattr(ev, "names", ()) or ())


def _event_text(ev) -> str | None:
    if isinstance(ev, str):
        return ev
    return getattr(ev, "text", None)


async def _run_turn(guide_client, turn_label: str, user_text: str, session) -> dict:
    """Drive one turn through the real stream_reply path and record the
    per-event timeline. `spoke_before_tool_call` is true if any spoken text
    arrived before a ToolCallStarted marker anywhere in the turn (reset
    after each marker, so it catches a mis-bet in *any* round of a
    multi-tool-call turn, not just the first) -- the predictor for the
    real-call failure mode where a caller hears a word start and then get
    cut off mid-word once the tool's answer arrives."""
    start = time.monotonic()
    delta_times: list[float] = []
    chars = 0
    tool_calls: list[dict] = []
    spoke_before_tool_call = False
    delta_since_marker = False
    text_parts: list[str] = []

    async for event in guide_client.stream_reply(user_text, session):
        t = time.monotonic() - start
        if _is_tool_call_event(event):
            if delta_since_marker:
                spoke_before_tool_call = True
            delta_since_marker = False
            tool_calls.append({"names": list(_tool_call_names(event)), "t": t})
            continue
        text = _event_text(event)
        if text is None:
            continue  # an event shape this script doesn't recognize
        delta_since_marker = True
        delta_times.append(t)
        chars += len(text)
        text_parts.append(text)

    t_first = delta_times[0] if delta_times else None
    t_last = delta_times[-1] if delta_times else None
    span = (t_last - t_first) if (t_first is not None and t_last is not None) else None
    return {
        "turn": turn_label,
        "prompt": user_text,
        "t_first_spoken": t_first,
        "t_last_spoken": t_last,
        "span": span,
        "n_delta_events": len(delta_times),
        "chars": chars,
        "tool_calls": tool_calls,
        "spoke_before_tool_call": spoke_before_tool_call,
        "text": "".join(text_parts),
    }


async def _run_rep(guide_client, rep_index: int) -> dict:
    session = guide_client.GuideSession()
    turns = []
    for label, prompt in _TURNS:
        turns.append(await _run_turn(guide_client, label, prompt, session))
        if session.conversation_id is None and not session.stream_missing_conversation:
            # Nothing to continue on -- avoid silently measuring N unrelated
            # fresh conversations instead of one real multi-turn call.
            print(
                f"WARNING: rep {rep_index} turn {label!r} ended with no conversation id; "
                "later turns in this rep may not be true continuations",
                file=sys.stderr,
            )
    return {"rep": rep_index, "turns": turns}


def _load_existing(path: Path, label: str) -> dict:
    if path.exists():
        data = json.loads(path.read_text())
        if data.get("label") != label:
            raise SystemExit(
                f"--out {path} already holds results for label {data.get('label')!r}, "
                f"not {label!r} -- pick a different --out or --label"
            )
        return data
    return {"label": label, "runs": []}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Path to the git worktree/checkout to measure")
    parser.add_argument("--label", required=True, help="Branch label recorded in the output JSON")
    parser.add_argument("--reps", type=int, default=1, help="Number of repetitions to run this invocation")
    parser.add_argument("--out", required=True, help="JSON file to write (or append to, with --append)")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to --out's existing runs instead of overwriting (used by compare_branches.py "
        "to interleave single reps across branches)",
    )
    parser.add_argument(
        "--rep-start-index",
        type=int,
        default=None,
        help="First rep index to record (defaults to len(existing runs) with --append, else 0)",
    )
    args = parser.parse_args()

    # Resolved before the chdir below -- a relative --out is meant to be
    # relative to the caller's cwd, not the worktree we're about to move
    # into to import its `app` package.
    out_path = Path(args.out).resolve()

    repo_path = str(Path(args.repo).resolve())
    sys.path.insert(0, repo_path)
    os.chdir(repo_path)

    from app import guide_client  # noqa: E402  (must import after sys.path/cwd are set)

    data = _load_existing(out_path, args.label) if args.append else {"label": args.label, "runs": []}
    start_index = args.rep_start_index if args.rep_start_index is not None else len(data["runs"])

    for i in range(args.reps):
        rep_index = start_index + i
        print(f"[{args.label}] running rep {rep_index}...", file=sys.stderr)
        result = asyncio.run(_run_rep(guide_client, rep_index))
        data["runs"].append(result)
        # Written after every rep, not just at the end -- a long comparison
        # run killed partway through still leaves usable results on disk.
        out_path.write_text(json.dumps(data, indent=2))

    _print_summary(data)


def _print_summary(data: dict) -> None:
    label = data["label"]
    by_turn: dict[str, list[dict]] = {}
    for run in data["runs"]:
        for turn in run["turns"]:
            by_turn.setdefault(turn["turn"], []).append(turn)

    print(f"\n=== {label}: {len(data['runs'])} rep(s) ===")
    print(f"{'turn':<12} {'t_first_med':>12} {'t_first_p90':>12} {'n_delta_med':>12} {'spoke_before_tool':>18}")
    for turn_label, _ in _TURNS:
        rows = by_turn.get(turn_label, [])
        firsts = sorted(r["t_first_spoken"] for r in rows if r["t_first_spoken"] is not None)
        n_deltas = sorted(r["n_delta_events"] for r in rows)
        mis_bets = sum(1 for r in rows if r["spoke_before_tool_call"])
        med_first = statistics.median(firsts) if firsts else float("nan")
        p90_first = firsts[min(len(firsts) - 1, int(len(firsts) * 0.9))] if firsts else float("nan")
        med_n = statistics.median(n_deltas) if n_deltas else float("nan")
        print(
            f"{turn_label:<12} {med_first:>12.3f} {p90_first:>12.3f} {med_n:>12.1f} "
            f"{mis_bets:>15}/{len(rows)}"
        )


if __name__ == "__main__":
    main()
