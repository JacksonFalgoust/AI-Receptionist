"""Three-way comparison of guide streaming behavior across main,
feature/live-token-streaming, and feature/trigger-phrase, against a live
GuideAnts guide.

Creates a separate git worktree per branch (in `--workdir`, default a repo-
local scratch dir), copies this repo's `.env` into each as a starting point,
then drives scripts/compare_streaming.py against each worktree, round-robin
across branches for `--reps` repetitions -- interleaved rather than one
branch finishing before the next starts, so GuideAnts/OpenRouter latency
drift (load, model warm state, etc.) is spread evenly across all three
instead of biasing whichever branch happens to run first or last.

Every worktree is added `--detach` at the branch's current commit, never as
a checkout of the branch ref itself -- git refuses a second checkout of a
branch that's already checked out elsewhere (the branch this repo's working
directory is currently on), and detached mode sidesteps that without
touching the current checkout. Worktrees are removed on exit unless --keep
is passed; results (one JSON per branch, plus this file's aggregate
markdown table) are left in place either way.

feature/trigger-phrase needs its own published guide (the "declare victory"
instruction only makes sense on that guide's prompt) -- pass its
publication id with --pub-id-trigger; that worktree's .env gets
GUIDEANTS_PUB_ID overridden to it after being copied from the template.

Usage:
    python scripts/compare_branches.py --pub-id-trigger <uuid> --reps 5

Not part of the app -- safe to delete once the three-way comparison is done.
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

_DEFAULT_BRANCHES = ["main", "feature/live-token-streaming", "feature/trigger-phrase"]

_TURN_ORDER = ["no_tool", "one_tool", "multi_tool"]


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, check=True, **kwargs)


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    )
    return Path(result.stdout.strip())


def _slug(branch: str) -> str:
    return branch.replace("/", "_")


def _existing_worktrees(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        line.split(" ", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    }


def _ensure_worktree(repo_root: Path, branch: str, path: Path) -> None:
    if str(path.resolve()) in _existing_worktrees(repo_root):
        print(f"Reusing existing worktree for {branch} at {path}", file=sys.stderr)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "-C", str(repo_root), "worktree", "add", "--detach", str(path), branch])


def _write_env(source_env: Path, dest_dir: Path, pub_id_override: str | None) -> None:
    if not source_env.exists():
        print(
            f"WARNING: {source_env} does not exist; {dest_dir} will have no .env -- "
            "guide_client._get_client() will raise on GUIDEANTS_PUB_ID",
            file=sys.stderr,
        )
        return
    text = source_env.read_text()
    if pub_id_override:
        if re.search(r"^GUIDEANTS_PUB_ID=.*$", text, flags=re.MULTILINE):
            text = re.sub(
                r"^GUIDEANTS_PUB_ID=.*$",
                f"GUIDEANTS_PUB_ID={pub_id_override}",
                text,
                flags=re.MULTILINE,
            )
        else:
            text += f"\nGUIDEANTS_PUB_ID={pub_id_override}\n"
    (dest_dir / ".env").write_text(text)


def _run_compare_streaming(
    compare_streaming_path: Path, worktree: Path, label: str, out_json: Path
) -> None:
    _run(
        [
            sys.executable,
            str(compare_streaming_path),
            "--repo",
            str(worktree),
            "--label",
            label,
            "--reps",
            "1",
            "--out",
            str(out_json),
            "--append",
        ]
    )


def _aggregate(out_json: Path) -> dict[str, dict]:
    data = json.loads(out_json.read_text())
    by_turn: dict[str, list[dict]] = {}
    for run in data["runs"]:
        for turn in run["turns"]:
            by_turn.setdefault(turn["turn"], []).append(turn)

    stats = {}
    for turn_label in _TURN_ORDER:
        rows = by_turn.get(turn_label, [])
        firsts = sorted(r["t_first_spoken"] for r in rows if r["t_first_spoken"] is not None)
        spans = sorted(r["span"] for r in rows if r["span"] is not None)
        n_deltas = sorted(r["n_delta_events"] for r in rows)
        chars = sorted(r["chars"] for r in rows)
        mis_bets = sum(1 for r in rows if r["spoke_before_tool_call"])

        def _p90(vals: list[float]) -> float:
            return vals[min(len(vals) - 1, int(len(vals) * 0.9))] if vals else float("nan")

        stats[turn_label] = {
            "n": len(rows),
            "t_first_med": statistics.median(firsts) if firsts else float("nan"),
            "t_first_p90": _p90(firsts),
            "span_med": statistics.median(spans) if spans else float("nan"),
            "n_delta_med": statistics.median(n_deltas) if n_deltas else float("nan"),
            "chars_med": statistics.median(chars) if chars else float("nan"),
            "mis_bets": mis_bets,
        }
    return stats


def _write_markdown_table(all_stats: dict[str, dict[str, dict]], out_md: Path) -> None:
    lines = [
        "# Streaming comparison: main vs feature/live-token-streaming vs feature/trigger-phrase",
        "",
        "Generated by scripts/compare_branches.py. `t_first` = time from request sent to the "
        "first spoken token reaching this app (what would be handed to Twilio); `mis_bets` = "
        "reps where spoken text preceded a tool call within the same turn -- the mid-word-cutoff "
        "predictor described in the plan. Discarded-narration counts are not observable from this "
        "offline harness (stream_reply never yields discarded text by design) -- see "
        "docs/STREAMING_COMPARISON.md's log-line list for those, gathered from a live call instead.",
        "",
    ]
    for turn_label in _TURN_ORDER:
        lines.append(f"## Turn: `{turn_label}`")
        lines.append("")
        lines.append(
            "| branch | n | t_first med (s) | t_first p90 (s) | span med (s) | "
            "delta events med | chars med | mis-bets |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for label, stats in all_stats.items():
            s = stats.get(turn_label, {})
            lines.append(
                f"| {label} | {s.get('n', 0)} | {s.get('t_first_med', float('nan')):.3f} | "
                f"{s.get('t_first_p90', float('nan')):.3f} | {s.get('span_med', float('nan')):.3f} | "
                f"{s.get('n_delta_med', float('nan')):.1f} | {s.get('chars_med', float('nan')):.0f} | "
                f"{s.get('mis_bets', 0)}/{s.get('n', 0)} |"
            )
        lines.append("")
    out_md.write_text("\n".join(lines))
    print(f"Wrote {out_md}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--branches", nargs="+", default=_DEFAULT_BRANCHES)
    parser.add_argument("--reps", type=int, default=5, help="Repetitions per branch, interleaved round-robin")
    parser.add_argument(
        "--workdir",
        default=None,
        help="Directory to hold worktrees + result JSON (default: <repo_root>/.compare-worktrees)",
    )
    parser.add_argument(
        "--pub-id-trigger",
        default=None,
        help="GUIDEANTS_PUB_ID for feature/trigger-phrase's published guide (overrides the .env template)",
    )
    parser.add_argument(
        "--source-env",
        default=None,
        help="Template .env to copy into every worktree (default: <repo_root>/.env)",
    )
    parser.add_argument("--keep", action="store_true", help="Don't remove worktrees on exit")
    args = parser.parse_args()

    repo_root = _repo_root()
    workdir = Path(args.workdir) if args.workdir else repo_root / ".compare-worktrees"
    source_env = Path(args.source_env) if args.source_env else repo_root / ".env"
    compare_streaming_path = Path(__file__).resolve().parent / "compare_streaming.py"

    trigger_branch = "feature/trigger-phrase"
    if trigger_branch in args.branches and not args.pub_id_trigger:
        print(
            f"WARNING: {trigger_branch} is in --branches but --pub-id-trigger was not given -- "
            "its worktree will use whatever GUIDEANTS_PUB_ID is in --source-env, which is "
            "probably the wrong guide for the 'declare victory' instruction",
            file=sys.stderr,
        )

    worktrees: dict[str, Path] = {}
    out_jsons: dict[str, Path] = {}
    try:
        for branch in args.branches:
            path = workdir / _slug(branch)
            _ensure_worktree(repo_root, branch, path)
            pub_id_override = args.pub_id_trigger if branch == trigger_branch else None
            _write_env(source_env, path, pub_id_override)
            worktrees[branch] = path
            out_jsons[branch] = workdir / f"results_{_slug(branch)}.json"

        for rep in range(args.reps):
            for branch in args.branches:
                print(f"--- rep {rep}: {branch} ---", file=sys.stderr)
                _run_compare_streaming(compare_streaming_path, worktrees[branch], branch, out_jsons[branch])

        all_stats = {branch: _aggregate(out_jsons[branch]) for branch in args.branches}
        _write_markdown_table(all_stats, workdir / "comparison.md")

        for branch, stats in all_stats.items():
            print(f"\n=== {branch} ===")
            for turn_label in _TURN_ORDER:
                s = stats.get(turn_label, {})
                print(
                    f"  {turn_label:<12} t_first_med={s.get('t_first_med', float('nan')):.3f}s  "
                    f"t_first_p90={s.get('t_first_p90', float('nan')):.3f}s  "
                    f"mis_bets={s.get('mis_bets', 0)}/{s.get('n', 0)}"
                )
    finally:
        if not args.keep:
            for branch, path in worktrees.items():
                print(f"Removing worktree {path}", file=sys.stderr)
                subprocess.run(
                    ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(path)],
                    check=False,
                )


if __name__ == "__main__":
    main()
