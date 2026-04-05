#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from projectlib import (
    ROOT,
    RESULTS_V2_TSV,
    archive_metrics,
    format_changed_files,
    git_short_head,
    now_iso,
    phase2_allowed_paths,
    run,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commit a kept phase 2 experiment safely and append its results row.")
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


def source_porcelain() -> list[str]:
    output = run(["git", "status", "--short"], cwd=ROOT).stdout
    return [line.rstrip("\n") for line in output.splitlines() if line.strip()]


def modified_paths(lines: list[str]) -> list[Path]:
    paths: list[Path] = []
    for line in lines:
        relative = line[3:]
        if " -> " in relative:
            relative = relative.split(" -> ", 1)[1]
        paths.append(ROOT / relative)
    return paths


def ensure_allowed(paths: list[Path]) -> None:
    allowed = phase2_allowed_paths()
    log_paths = {RESULTS_V2_TSV.resolve()}
    disallowed = sorted(
        path.relative_to(ROOT).as_posix()
        for path in paths
        if path.resolve() not in log_paths and path not in allowed
    )
    if disallowed:
        raise SystemExit(
            "Refusing to keep experiment because files outside the phase 2 allowlist are modified:\n"
            + "\n".join(disallowed)
        )


def append_results_row(status: str, description: str, commit: str, metrics_path: Path, changed_files: str) -> None:
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
            "--changed-files",
            changed_files,
        ],
        cwd=ROOT,
        check=True,
        text=True,
    )


def changed_files_for_head() -> str:
    output = run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], cwd=ROOT).stdout
    files = [ROOT / line.strip() for line in output.splitlines() if line.strip()]
    return format_changed_files(files)


def main() -> None:
    args = parse_args()
    metrics_path = (ROOT / args.metrics).resolve() if not Path(args.metrics).is_absolute() else Path(args.metrics)
    if not metrics_path.exists():
        raise SystemExit(f"Metrics file not found: {metrics_path}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    if args.status == "keep" and not metrics["decision"]["keep_eligible"]:
        raise SystemExit("Refusing to record keep because metrics.json says the experiment is not keep-eligible.")

    status_lines = source_porcelain()
    changed_paths = modified_paths(status_lines)
    ensure_allowed(changed_paths)

    if args.status == "keep" and not changed_paths:
        raise SystemExit("Refusing to record keep because no tracked allowlisted files are modified.")

    if changed_paths:
        commit_message = args.commit_message or f"Keep experiment: {args.description}"
        run(["git", "add", *[path.relative_to(ROOT).as_posix() for path in changed_paths]], cwd=ROOT)
        run(["git", "commit", "-m", commit_message], cwd=ROOT)

    commit = git_short_head()
    changed_files = changed_files_for_head() if changed_paths else "-"
    archive_metrics(metrics_path, commit)
    append_results_row(args.status, args.description, commit, metrics_path, changed_files)
    print(f"Recorded {args.status} at commit {commit} on {now_iso()}")


if __name__ == "__main__":
    main()
