#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from projectlib import RESULTS_V2_TSV, ensure_results_v2, git_short_head, load_phase2_policy, now_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append one experiment row to results_v2.tsv")
    parser.add_argument("--description", required=True, help="Short experiment description")
    parser.add_argument(
        "--status",
        required=True,
        choices=["baseline", "keep", "discard", "crash"],
        help="Experiment outcome status",
    )
    parser.add_argument(
        "--metrics",
        default="experiments/current/metrics.json",
        help="Path to metrics.json from evaluate.py",
    )
    parser.add_argument(
        "--commit",
        default=None,
        help="Commit hash to record. Defaults to current git short HEAD.",
    )
    parser.add_argument(
        "--changed-files",
        default="-",
        help="Comma-separated changed file list to store with the row.",
    )
    return parser.parse_args()


def crash_row(commit: str, description: str, changed_files: str) -> str:
    score_version = load_phase2_policy()["SCORE_VERSION"]
    return "\t".join(
        [
            commit,
            now_iso(),
            description,
            score_version,
            "0.000000",
            "0.000000",
            "0.000000",
            "0.000000",
            "0.000000",
            "0.000000",
            "0.000000",
            changed_files,
            "crash",
        ]
    )


def scored_row(commit: str, description: str, status: str, metrics_path: Path, changed_files: str) -> str:
    if not metrics_path.exists():
        raise SystemExit(f"Metrics file not found: {metrics_path}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    development = metrics["development"]["summary"]
    holdout = metrics["holdout"]["summary"]
    decision = metrics["decision"]
    return "\t".join(
        [
            commit,
            now_iso(),
            description,
            metrics["score_version"],
            f"{decision['development_score']:.6f}",
            f"{decision['holdout_score']:.6f}",
            f"{decision['overall_score']:.6f}",
            f"{development['ssim_avg']:.6f}",
            f"{development['video_bytes_ratio_avg']:.6f}",
            f"{holdout['ssim_avg']:.6f}",
            f"{holdout['video_bytes_ratio_avg']:.6f}",
            changed_files,
            status,
        ]
    )


def main() -> None:
    args = parse_args()
    commit = args.commit or git_short_head()
    changed_files = args.changed_files or "-"
    if args.status == "crash":
        row = crash_row(commit, args.description, changed_files)
    else:
        row = scored_row(commit, args.description, args.status, Path(args.metrics), changed_files)

    ensure_results_v2()
    with RESULTS_V2_TSV.open("a", encoding="utf-8") as handle:
        handle.write(row + "\n")
    print(row)


if __name__ == "__main__":
    main()
