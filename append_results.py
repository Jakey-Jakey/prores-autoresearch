#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from projectlib import RESULTS_TSV, git_short_head, now_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append one experiment row to results.tsv")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    commit = args.commit or git_short_head()

    if args.status == "crash":
        row = "\t".join([commit, now_iso(), args.description, "0.000000", "0.0000", "0.000000", "0.000000", "crash"])
    else:
        metrics_path = Path(args.metrics)
        if not metrics_path.exists():
            raise SystemExit(f"Metrics file not found: {metrics_path}")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        summary = metrics["summary"]
        row = "\t".join(
            [
                commit,
                now_iso(),
                args.description,
                f"{summary['ssim_avg']:.6f}",
                f"{summary['psnr_avg']:.4f}",
                f"{summary['video_bytes_ratio_avg']:.6f}",
                f"{summary['composite_score']:.6f}",
                args.status,
            ]
        )

    with RESULTS_TSV.open("a", encoding="utf-8") as handle:
        handle.write(row + "\n")
    print(row)


if __name__ == "__main__":
    main()
