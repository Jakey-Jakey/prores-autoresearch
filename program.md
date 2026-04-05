# ProRes Autoresearch Program

Read this file and the project docs before starting experiments.

## Scope

- Read `README.md`, `meta/source_notes.md`, and `encoder_params.py` first.
- Only modify `encoder_params.py`.
- Do not edit `prepare.py`, `build.py`, `evaluate.py`, `run_experiment.sh`, or FFmpeg source files directly.
- Do not expand scope into 4444, XQ, alpha, vendor tagging, entropy tables, or structural C changes in phase 1.

## Experiment Loop

1. Inspect the current best rows in `results.tsv`.
2. Make one conceptual change in `encoder_params.py`.
3. Run `bash run_experiment.sh`.
4. Read `experiments/current/eval.log` and `experiments/current/metrics.json`.
5. If `composite_score` improves, keep the edit and commit it.
6. If it does not improve, restore the mutable file with `git restore encoder_params.py`.
7. Append a row to `results.tsv` with `python3 append_results.py --description "..." --status keep|discard|crash`.
8. Continue.

## Revert Policy

- Never commit losing experiments.
- Use `git restore encoder_params.py` for routine reverts.
- Do not use destructive resets for normal loop control.

## Optimization Target

Optimize the global average `composite_score`, where:

- decoded-output similarity to Apple is measured with SSIM
- rate matching is measured by video packet bytes only
- PSNR is reported for context but is not the target

## Strategy Order

Prioritize changes in this order:

1. per-profile luma/chroma matrices
2. per-profile `br_tab`
3. per-profile `min_quant` and `max_quant`
4. `PRORES_MB_LIMITS`
5. `RUNTIME_DEFAULTS["bits_per_mb_override"]`

`RUNTIME_DEFAULTS["mbs_per_slice"]` is also in scope, but change it carefully because it affects all cases at once.

## Plateau Policy

If improvements stop after many attempts, note that phase 1 may be exhausted rather than breaking the harness. Raw C editing and codebook changes are phase 2 work, not phase 1 work.
