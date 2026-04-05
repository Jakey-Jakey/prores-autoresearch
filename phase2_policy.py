SCORE_VERSION = "phase2_v1"

DEVELOPMENT_PACK = "development"
HOLDOUT_PACK = "holdout"

CLIP_PACKS = {
    "development": [
        "bars.mkv",
        "detail.mkv",
        "gradient.mkv",
        "motion.mkv",
        "realworld_tos_action.mkv",
        "realworld_tos_dialogue.mkv",
    ],
    "holdout": [
        "realworld_tos_holdout_midaction.mkv",
        "realworld_tos_holdout_opening.mkv",
    ],
}

HOLDOUT_GENERATION_SPECS = [
    {
        "filename": "realworld_tos_holdout_opening.mkv",
        "start_time": "00:00:47.0",
    },
    {
        "filename": "realworld_tos_holdout_midaction.mkv",
        "start_time": "00:04:42.0",
    },
]

SCORE_WEIGHTS = {
    "development": 0.80,
    "holdout": 0.20,
}

GATES = {
    "max_holdout_score_drop": 0.0005,
    "max_holdout_case_drop": 0.0010,
}

ALLOWED_PROJECT_FILES = [
    ".gitignore",
    "README.md",
    "append_results.py",
    "build.py",
    "discard_experiment.py",
    "encoder_params.py",
    "evaluate.py",
    "ffmpeg_overrides",
    "keep_experiment.py",
    "meta/source_notes.md",
    "patch_bases/proresdata.c.orig",
    "patch_bases/proresenc_kostya_common.h.orig",
    "phase2_policy.py",
    "prepare.py",
    "program.md",
    "projectlib.py",
    "run_experiment.sh",
]

ALLOWED_OVERRIDE_FILES = [
    "ffmpeg_overrides/libavcodec/proresdata.c",
    "ffmpeg_overrides/libavcodec/proresenc_kostya.c",
    "ffmpeg_overrides/libavcodec/proresenc_kostya_common.c",
    "ffmpeg_overrides/libavcodec/proresenc_kostya_common.h",
]
