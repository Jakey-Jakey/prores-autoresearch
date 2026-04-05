# ProRes Autoresearch Phase 2 Program

Read this file, `README.md`, `meta/source_notes.md`, `phase2_policy.py`, and `encoder_params.py` before starting experiments.

## Scope

- You may modify only the allowlisted project files and override templates declared in `phase2_policy.py`.
- You may edit `encoder_params.py` and the tracked ProRes override templates in `ffmpeg_overrides/libavcodec/`.
- Do not edit `ffmpeg_source/` directly.
- Stay in 4:2:2 scope. Do not expand into 4444, XQ, alpha, vendor tagging, or unrelated FFmpeg subsystems.
- Keep the FFmpeg pin, reference encoder, clip source list, and score-v2 structure intact unless phase policy is intentionally revised first.

## Experiment Loop

1. Inspect `results_v2.tsv`. Treat the latest `baseline` or `keep` row as the incumbent.
2. Make one conceptual change across the allowlisted phase 2 files.
3. Run `bash run_experiment.sh`.
4. Read `experiments/current/eval.log` and `experiments/current/metrics.json`.
5. If `metrics.json` says `keep_eligible = yes` and the change is genuinely better, run `python3 keep_experiment.py --description "..."`.
6. If it is not better, run `python3 discard_experiment.py --description "..." --status discard`.
7. If the run crashes after a real attempt, run `python3 discard_experiment.py --description "..." --status crash`.
8. Continue.

## Revert Policy

- Never commit losing experiments.
- Do not use raw `git restore` during the normal loop; use `discard_experiment.py` so the result is logged before files are restored.
- Do not use destructive resets for loop control.

## Workflow Helpers

- `keep_experiment.py` commits all tracked allowlisted source edits, archives `metrics.json`, then appends the real commit to `results_v2.tsv`.
- `discard_experiment.py` logs the discard or crash first, then restores tracked allowlisted source edits back to `HEAD`.
- `append_results.py` still exists as the low-level logger, but normal runs should use the keep/discard wrappers.

## Optimization Target

Phase 2 evaluates two packs:

- development pack: the original 6 clips
- holdout pack: the 2 holdout `Tears of Steel` clips

Case scoring remains:

- `case_score = SSIM * max(0, 1 - 0.20 * abs(log2(video_bytes_ratio)))`

Decision scoring is:

- `development_score = mean(case_score over the development pack)`
- `holdout_score = mean(case_score over the holdout pack)`
- `overall_score = 0.80 * development_score + 0.20 * holdout_score`

## Keep Gates

A keep must satisfy all of these:

- `overall_score` improves over the incumbent
- `holdout_score` does not drop by more than `0.0005`
- no single holdout case drops by more than `0.0010`

If any gate fails, discard the experiment.

## Strategy Order

Prioritize changes in this order:

1. `proresenc_kostya.c` behavior: slice quant selection, rate/distortion logic, luma/chroma handling, deadzones, overquant behavior
2. `proresenc_kostya_common.c` and `proresenc_kostya_common.h`: shared ProRes setup and profile behavior
3. `proresdata.c`: scan/codebook behavior after codec-logic changes plateau
4. `encoder_params.py` and `phase2_policy.py` only when they unlock a more meaningful codec experiment

## Guardrails

- Do not edit files outside the allowlist in `phase2_policy.py`.
- Do not change the metric formula or clip packs mid-campaign.
- Do not bypass the holdout gate because of a development-only win.
