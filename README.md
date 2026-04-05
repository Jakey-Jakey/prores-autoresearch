# ProRes Autoresearch

This project is a standalone autoresearch-style harness for tuning FFmpeg's `prores_ks` encoder toward Apple's `prores_videotoolbox` behavior on macOS.

The fixed infrastructure lives in:

- `prepare.py` for one-time setup, source pinning, clip generation, and Apple reference generation
- `build.py` for validating `encoder_params.py`, patching upstream FFmpeg source, and rebuilding
- `evaluate.py` for candidate encoding plus scoring
- `run_experiment.sh` for a single build-and-evaluate cycle

The only file intended for routine experimental edits is `encoder_params.py`.

## Quick start

```bash
python3 prepare.py
python3 build.py
bash run_experiment.sh
```

Read `program.md` before starting autonomous experiments.
