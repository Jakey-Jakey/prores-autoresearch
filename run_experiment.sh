#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

python3 build.py
rm -rf experiments/current
mkdir -p experiments/current
python3 evaluate.py --experiment-dir experiments/current > experiments/current/eval.log 2>&1
grep '^FINAL_METRIC ' experiments/current/eval.log | tail -n 1
