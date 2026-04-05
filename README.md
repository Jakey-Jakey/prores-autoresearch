# ProRes Autoresearch

This project is a standalone autoresearch-style harness for tuning FFmpeg's `prores_ks` encoder toward Apple's `prores_videotoolbox` behavior on macOS.

The fixed infrastructure lives in:

- `prepare.py` for one-time setup, source pinning, clip generation, and Apple reference generation
- `build.py` for validating `encoder_params.py`, patching upstream FFmpeg source, and rebuilding
- `evaluate.py` for candidate encoding plus scoring
- `run_experiment.sh` for a single build-and-evaluate cycle
- `keep_experiment.py` for safely committing a winning experiment and logging it
- `discard_experiment.py` for safely logging and reverting a losing or crashed experiment

The only file intended for routine experimental edits is `encoder_params.py`.

## Quick start

```bash
python3 prepare.py
python3 build.py
bash run_experiment.sh
```

Read `program.md` before starting autonomous experiments.

To append a scored run to `results.tsv`, use:

```bash
python3 append_results.py --description "..." --status keep
```

For normal autonomous operation, prefer the higher-level helpers instead:

```bash
python3 keep_experiment.py --description "raise hq br_tab"
python3 discard_experiment.py --description "lower lt br_tab" --status discard
python3 discard_experiment.py --description "bad matrix experiment" --status crash
```
