#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from projectlib import ENCODER_PARAMS_PATH, ROOT, run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log a discarded or crashed experiment and restore encoder_params.py.")
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


def main() -> None:
    args = parse_args()
    if args.status == "discard":
        metrics_path = (ROOT / args.metrics).resolve() if not Path(args.metrics).is_absolute() else Path(args.metrics)
        if not metrics_path.exists():
            raise SystemExit(f"Metrics file not found for discard case: {metrics_path}")
        subprocess.run(
            [
                "python3",
                str(ROOT / "append_results.py"),
                "--description",
                args.description,
                "--status",
                "discard",
                "--metrics",
                str(metrics_path),
            ],
            cwd=ROOT,
            check=True,
            text=True,
        )
    else:
        subprocess.run(
            [
                "python3",
                str(ROOT / "append_results.py"),
                "--description",
                args.description,
                "--status",
                "crash",
            ],
            cwd=ROOT,
            check=True,
            text=True,
        )

    run(["git", "restore", ENCODER_PARAMS_PATH.name], cwd=ROOT)
    print(f"Restored {ENCODER_PARAMS_PATH.name} to HEAD after recording {args.status}.")


if __name__ == "__main__":
    main()
