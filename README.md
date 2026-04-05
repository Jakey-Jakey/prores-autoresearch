# ProRes Autoresearch Phase 2

This worktree is the phase 2 harness for tuning FFmpeg's `prores_ks` encoder toward Apple's `prores_videotoolbox` behavior on macOS.

Phase 2 starts from the current incumbent encoder state and expands the editable surface from one parameter file to a guardrailed set of harness files plus tracked ProRes codec override templates.

The fixed infrastructure lives in:

- `prepare.py` for one-time setup, source pinning, clip generation, override seeding, and Apple reference generation
- `build.py` for validating `encoder_params.py`, restoring upstream snapshots, applying parameterized patches, overlaying tracked overrides, and rebuilding
- `evaluate.py` for development-pack and holdout-pack scoring
- `run_experiment.sh` for a single build-and-evaluate cycle
- `keep_experiment.py` for safely committing a winning or baseline phase 2 experiment and logging it to `results_v2.tsv`
- `discard_experiment.py` for safely logging and reverting a losing or crashed experiment
- `phase2_policy.py` for the editable surface allowlist, clip packs, score version, and keep gates

Phase 2 editable source files are:

- project files listed in `phase2_policy.py`
- tracked codec override templates in `ffmpeg_overrides/libavcodec/`

Do not edit `ffmpeg_source/` directly.

## Quick Start

```bash
python3 prepare.py
bash run_experiment.sh
```

To establish or refresh the active phase 2 incumbent row:

```bash
python3 keep_experiment.py --description "baseline_phase2_v1" --status baseline
```

For normal autonomous operation:

```bash
python3 keep_experiment.py --description "..."
python3 discard_experiment.py --description "..." --status discard
python3 discard_experiment.py --description "..." --status crash
```

Phase 2 results are recorded in `results_v2.tsv`. The legacy `results.tsv` remains as the phase 1 archive.
