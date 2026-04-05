# ProRes Autoresearch Program

Read this file and the project docs before starting experiments.

## Scope

- Read `README.md`, `meta/source_notes.md`, and `encoder_params.py` first.
- Only modify `encoder_params.py`.
- Do not edit `prepare.py`, `build.py`, `evaluate.py`, `run_experiment.sh`, or FFmpeg source files directly.
- Do not expand scope into 4444, XQ, alpha, vendor tagging, entropy tables, or structural C changes in phase 1.

## Experiment Loop

1. Inspect `results.tsv`, treating the latest `baseline` row as the starting point for the campaign and the best `keep` row as the current incumbent after experiments begin.
2. Make one conceptual change in `encoder_params.py`.
3. Run `bash run_experiment.sh`.
4. Read `experiments/current/eval.log` and `experiments/current/metrics.json`.
5. If `composite_score` improves, run `python3 keep_experiment.py --description "..."`.
6. If it does not improve, run `python3 discard_experiment.py --description "..." --status discard`.
7. If the run crashes after a real attempt, run `python3 discard_experiment.py --description "..." --status crash`.
8. Continue.

## Revert Policy

- Never commit losing experiments.
- Do not use raw `git restore encoder_params.py` during the normal loop; use `discard_experiment.py` so the result is logged before the file is restored.
- Do not use destructive resets for normal loop control.

## Workflow Helpers

- `keep_experiment.py` makes the keep path atomic: it commits `encoder_params.py` first, then appends the results row with the real commit hash.
- `discard_experiment.py` makes the discard path atomic: it logs the experiment result first, then restores `encoder_params.py` from `HEAD`.
- `append_results.py` still exists as a low-level helper, but normal autonomous runs should prefer the keep/discard wrappers.

## Optimization Target

Optimize the global average `composite_score`, where:

- decoded-output similarity to Apple is measured with SSIM
- rate matching is measured by video packet bytes only
- PSNR is reported for context but is not the target

## Strategy Order

Prioritize changes in this order:

1. per-profile luma/chroma matrices
2. per-profile `br_tab`
3. per-profile `CHROMA_QUANT_SCALE`
4. `SEARCH_TUNING["luma_error_weight_percent"]` and `SEARCH_TUNING["chroma_error_weight_percent"]`
5. `SEARCH_TUNING["overquant_penalty"]`
6. `SEARCH_TUNING["ac_deadzone_percent"]`
7. per-profile `min_quant` and `max_quant`
8. `PRORES_MB_LIMITS`
9. `RUNTIME_DEFAULTS["bits_per_mb_override"]`

`RUNTIME_DEFAULTS["mbs_per_slice"]` is also in scope, but change it carefully because it affects all cases at once.

## Plateau Policy

If improvements stop after many attempts, note that phase 1 may be exhausted rather than breaking the harness. Raw C editing and codebook changes are phase 2 work, not phase 1 work.
