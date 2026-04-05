#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from projectlib import ENCODER_PARAMS_PATH, ROOT, git_short_head, now_iso, run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commit a kept experiment safely and append its results row.")
    parser.add_argument("--description", required=True, help="Short experiment description.")
    parser.add_argument(
        "--status",
        default="keep",
        choices=["keep", "baseline"],
        help="Use baseline only when intentionally recording a new baseline.",
    )
    parser.add_argument(
        "--metrics",
        default="experiments/current/metrics.json",
        help="Path to evaluate.py metrics output.",
    )
    parser.add_argument(
        "--commit-message",
        default=None,
        help="Optional git commit message. Defaults to a message derived from the description.",
    )
    return parser.parse_args()


def git_porcelain() -> list[str]:
    output = run(["git", "status", "--short"], cwd=ROOT).stdout
    return [line.rstrip("\n") for line in output.splitlines() if line.strip()]


def only_encoder_params_changed(lines: list[str]) -> bool:
    allowed = {f" M {ENCODER_PARAMS_PATH.name}", f"M  {ENCODER_PARAMS_PATH.name}", f"MM {ENCODER_PARAMS_PATH.name}", f"?? {ENCODER_PARAMS_PATH.name}"}
    return all(line in allowed for line in lines)


def append_results_row(status: str, description: str, commit: str, metrics_path: Path) -> None:
    subprocess.run(
        [
            "python3",
            str(ROOT / "append_results.py"),
            "--description",
            description,
            "--status",
            status,
            "--commit",
            commit,
            "--metrics",
            str(metrics_path),
        ],
        cwd=ROOT,
        check=True,
        text=True,
    )


def main() -> None:
    args = parse_args()
    metrics_path = (ROOT / args.metrics).resolve() if not Path(args.metrics).is_absolute() else Path(args.metrics)
    if not metrics_path.exists():
        raise SystemExit(f"Metrics file not found: {metrics_path}")
    json.loads(metrics_path.read_text(encoding="utf-8"))

    status_lines = git_porcelain()
    if status_lines and not only_encoder_params_changed(status_lines):
        raise SystemExit(
            "Refusing to keep experiment because files other than encoder_params.py are modified.\n"
            "Clean the worktree or handle those changes separately first."
        )

    if status_lines:
        commit_message = args.commit_message or f"Keep experiment: {args.description}"
        run(["git", "add", ENCODER_PARAMS_PATH.name], cwd=ROOT)
        run(["git", "commit", "-m", commit_message], cwd=ROOT)

    commit = git_short_head()
    append_results_row(args.status, args.description, commit, metrics_path)
    print(f"Recorded {args.status} at commit {commit} on {now_iso()}")


if __name__ == "__main__":
    main()
