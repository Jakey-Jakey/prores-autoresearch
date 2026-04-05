#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from projectlib import ROOT, RESULTS_V2_TSV, format_changed_files, phase2_allowed_paths, run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log a discarded or crashed phase 2 experiment and restore allowlisted files.")
    parser.add_argument("--description", required=True, help="Short experiment description.")
    parser.add_argument(
        "--status",
        required=True,
        choices=["discard", "crash"],
        help="discard uses current metrics; crash records zero metrics.",
    )
    parser.add_argument(
        "--metrics",
        default="experiments/current/metrics.json",
        help="Path to evaluate.py metrics output for discard cases.",
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
            "Refusing to discard experiment because files outside the phase 2 allowlist are modified:\n"
            + "\n".join(disallowed)
        )


def append_results_row(status: str, description: str, metrics_path: Path | None, changed_files: str) -> None:
    command = [
        "python3",
        str(ROOT / "append_results.py"),
        "--description",
        description,
        "--status",
        status,
        "--changed-files",
        changed_files,
    ]
    if metrics_path is not None:
        command.extend(["--metrics", str(metrics_path)])
    subprocess.run(command, cwd=ROOT, check=True, text=True)


def main() -> None:
    args = parse_args()
    status_lines = source_porcelain()
    changed_paths = modified_paths(status_lines)
    ensure_allowed(changed_paths)
    changed_files = format_changed_files(changed_paths)

    metrics_path: Path | None = None
    if args.status == "discard":
        metrics_path = (ROOT / args.metrics).resolve() if not Path(args.metrics).is_absolute() else Path(args.metrics)
        if not metrics_path.exists():
            raise SystemExit(f"Metrics file not found for discard case: {metrics_path}")
    append_results_row(args.status, args.description, metrics_path, changed_files)

    tracked_paths = [
        path
        for line, path in zip(status_lines, changed_paths)
        if not line.startswith("??") and path.resolve() != RESULTS_V2_TSV.resolve()
    ]
    untracked_paths = [path for line, path in zip(status_lines, changed_paths) if line.startswith("??")]
    if tracked_paths:
        run(["git", "restore", *[path.relative_to(ROOT).as_posix() for path in tracked_paths]], cwd=ROOT)
    if untracked_paths:
        run(["git", "clean", "-fd", "--", *[path.relative_to(ROOT).as_posix() for path in untracked_paths]], cwd=ROOT)
    print(f"Restored allowlisted tracked files to HEAD after recording {args.status}.")


if __name__ == "__main__":
    main()
