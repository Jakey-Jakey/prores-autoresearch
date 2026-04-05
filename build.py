#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from projectlib import (
    ENCODER_PARAMS_PATH,
    FFMPEG_SOURCE_DIR,
    DIRECT_OVERRIDE_KEYS,
    candidate_paths,
    load_encoder_params,
    patch_kostya_source,
    parse_source_baseline,
    patch_common_source,
    run,
    validate_params,
    write_text,
)

CONFIGURE_FLAGS = [
    "--disable-doc",
    "--disable-debug",
    "--disable-ffplay",
    "--disable-network",
    "--disable-devices",
    "--disable-hwaccels",
]


def restore_patch_targets() -> None:
    paths = candidate_paths()
    for key in ["common", "kostya", "common_h", "proresdata"]:
        paths[key].write_text(paths[f"{key}_orig"].read_text(encoding="utf-8"), encoding="utf-8")


def patch_sources() -> None:
    params = load_encoder_params()
    validate_params(params)
    paths = candidate_paths()
    base_text = paths["common_override"].read_text(encoding="utf-8")
    baseline = parse_source_baseline(base_text)
    patched_text = patch_common_source(base_text, params, baseline)
    paths["common"].write_text(patched_text, encoding="utf-8")
    kostya_base_text = paths["kostya_override"].read_text(encoding="utf-8")
    patched_kostya_text = patch_kostya_source(kostya_base_text, params)
    paths["kostya"].write_text(patched_kostya_text, encoding="utf-8")
    for key in DIRECT_OVERRIDE_KEYS:
        paths[key].write_text(paths[f"{key}_override"].read_text(encoding="utf-8"), encoding="utf-8")


def ensure_configure() -> None:
    stamp_path = FFMPEG_SOURCE_DIR / ".configure-flags"
    desired = "\n".join(CONFIGURE_FLAGS) + "\n"
    config_exists = (FFMPEG_SOURCE_DIR / "ffbuild" / "config.mak").exists()
    if config_exists and stamp_path.exists() and stamp_path.read_text(encoding="utf-8") == desired:
        return
    if config_exists:
        run(["make", "distclean"], cwd=FFMPEG_SOURCE_DIR)
    run(["./configure", *CONFIGURE_FLAGS], cwd=FFMPEG_SOURCE_DIR)
    write_text(stamp_path, desired)


def build_ffmpeg() -> None:
    jobs = str(os.cpu_count() or 4)
    run(["make", f"-j{jobs}", "ffmpeg", "ffprobe"], cwd=FFMPEG_SOURCE_DIR)
    ffmpeg_bin = FFMPEG_SOURCE_DIR / "ffmpeg"
    if not ffmpeg_bin.exists():
        raise SystemExit("Custom FFmpeg build did not produce an ffmpeg binary")
    encoders = run([str(ffmpeg_bin), "-hide_banner", "-encoders"]).stdout
    if "prores_ks" not in encoders:
        raise SystemExit("Custom FFmpeg build is missing prores_ks")


def main() -> None:
    if not ENCODER_PARAMS_PATH.exists():
        raise SystemExit("encoder_params.py is missing; run prepare.py first")
    restore_patch_targets()
    patch_sources()
    ensure_configure()
    build_ffmpeg()
    print("build.py completed successfully")


if __name__ == "__main__":
    main()
