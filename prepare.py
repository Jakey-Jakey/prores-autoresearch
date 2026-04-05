#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from projectlib import (
    ENCODER_PARAMS_PATH,
    FFMPEG_EXPECTED_COMMIT,
    FFMPEG_REMOTE,
    FFMPEG_SOURCE_DIR,
    FFMPEG_TAG,
    META_DIR,
    PATCH_BASES_DIR,
    PHASE1_PROFILES,
    REFERENCE_DIR,
    RESULTS_TSV,
    TEST_CLIPS_DIR,
    candidate_paths,
    ensure_dirs,
    find_command,
    list_test_clips,
    maybe_write_text,
    parse_source_baseline,
    reference_path,
    render_encoder_params,
    run,
    write_environment_json,
    write_text,
)


REAL_WORLD_SOURCES = [
    {
        "name": "tears_of_steel",
        "url": "https://download.blender.org/demo/movies/ToS/tears_of_steel_1080p.mov",
        "license_note": "Blender Foundation Tears of Steel sample, CC BY 3.0.",
    },
    {
        "name": "sintel",
        "url": "https://download.blender.org/durian/trailer/sintel_trailer-1080p.mp4",
        "license_note": "Blender Foundation Sintel trailer, CC BY 3.0.",
    },
    {
        "name": "big_buck_bunny",
        "url": "https://download.blender.org/peach/bigbuckbunny_movies/big_buck_bunny_1080p_h264.mov",
        "license_note": "Blender Foundation Big Buck Bunny sample, CC BY 3.0.",
    },
]

def local_real_world_candidates() -> list[Path]:
    downloads_dir = Path.home() / "Downloads"
    candidates = [
        downloads_dir / "tears_of_steel_1080p.mov",
        downloads_dir / "Tears_of_Steel_1080p.mov",
    ]
    workspace_parent = TEST_CLIPS_DIR.parent.parent
    for sibling_name in [
        "prores-autoresearch",
        "prores-autoresearch-agent",
        "prores-autoresearch-phase2",
    ]:
        candidates.append(workspace_parent / sibling_name / "test_clips" / "_downloads" / "tears_of_steel_1080p.mov")
    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped

REAL_WORLD_CLIP_SPECS = [
    ("realworld_tos_dialogue.mkv", "00:02:10.0"),
    ("realworld_tos_action.mkv", "00:07:18.0"),
]


def verify_commands() -> None:
    for command in ["ffmpeg", "ffprobe", "git", "python3", "clang", "make"]:
        find_command(command)
    encoders = run(["ffmpeg", "-hide_banner", "-encoders"]).stdout
    if "prores_videotoolbox" not in encoders:
        raise SystemExit("Blocked: system ffmpeg does not expose prores_videotoolbox")


def ensure_ffmpeg_source() -> None:
    if not FFMPEG_SOURCE_DIR.exists():
        run(["git", "clone", "--depth", "1", "--branch", FFMPEG_TAG, FFMPEG_REMOTE, str(FFMPEG_SOURCE_DIR)])
    commit = run(["git", "-C", str(FFMPEG_SOURCE_DIR), "rev-parse", "HEAD"]).stdout.strip()
    if commit != FFMPEG_EXPECTED_COMMIT:
        raise SystemExit(f"Blocked: ffmpeg_source is at {commit}, expected {FFMPEG_EXPECTED_COMMIT}")
    write_text(META_DIR / "ffmpeg_commit.txt", commit + "\n")


def snapshot_patch_bases() -> None:
    paths = candidate_paths()
    for source_key, dest_key in [("common", "common_orig"), ("kostya", "kostya_orig")]:
        source = paths[source_key]
        dest = paths[dest_key]
        if not dest.exists():
            dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def extract_baseline_encoder_params() -> None:
    if ENCODER_PARAMS_PATH.exists():
        return
    common_orig = candidate_paths()["common_orig"]
    baseline = parse_source_baseline(common_orig.read_text(encoding="utf-8"))
    write_text(ENCODER_PARAMS_PATH, render_encoder_params(baseline["baseline_encoder_params"]))


def make_gradient_clip(output_path: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "nullsrc=s=1920x1080:r=24000/1001,geq=lum='X/W*1023':cb='Y/H*1023':cr='(X+Y)/(W+H)*1023'",
            "-t",
            "2",
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "yuv422p10le",
            str(output_path),
        ]
    )


def make_detail_clip(output_path: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "mandelbrot=s=1920x1080:r=24000/1001",
            "-t",
            "2",
            "-c:v",
            "ffv1",
            "-vf",
            "format=yuv422p10le",
            str(output_path),
        ]
    )


def make_motion_clip(output_path: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=1920x1080:r=24000/1001",
            "-t",
            "2",
            "-c:v",
            "ffv1",
            "-vf",
            "format=yuv422p10le",
            str(output_path),
        ]
    )


def make_bars_clip(output_path: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "smptehdbars=s=1920x1080:r=24000/1001",
            "-t",
            "2",
            "-c:v",
            "ffv1",
            "-vf",
            "format=yuv422p10le",
            str(output_path),
        ]
    )


def download_real_world_source(download_dir: Path) -> tuple[Path | None, str]:
    download_dir.mkdir(parents=True, exist_ok=True)
    for source in REAL_WORLD_SOURCES:
        destination = download_dir / Path(source["url"]).name
        if not destination.exists():
            try:
                with urllib.request.urlopen(source["url"], timeout=30) as response:
                    destination.write_bytes(response.read())
            except Exception:
                if source["name"] == "tears_of_steel":
                    for candidate in local_real_world_candidates():
                        if candidate.exists() and candidate.stat().st_size > 0:
                            if candidate.resolve() != destination.resolve():
                                candidate.rename(destination)
                            return (
                                destination,
                                "Blender Foundation Tears of Steel sample, CC BY 3.0. Official fetch failed, so setup fell back to a local download.",
                            )
                continue
        if destination.exists() and destination.stat().st_size > 0:
            return destination, source["license_note"]
    return None, "No real-world clip downloaded. Network fetch failed."


def make_real_world_clip(output_path: Path, source_path: Path, start_time: str) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            start_time,
            "-t",
            "2.0",
            "-i",
            str(source_path),
            "-c:v",
            "ffv1",
            "-vf",
            "fps=24000/1001,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv422p10le",
            str(output_path),
        ]
    )


def generate_real_world_clips() -> str:
    download_dir = TEST_CLIPS_DIR / "_downloads"
    source_path, note = download_real_world_source(download_dir)
    if source_path is None:
        return note
    created = []
    for filename, start_time in REAL_WORLD_CLIP_SPECS:
        output_path = TEST_CLIPS_DIR / filename
        if not output_path.exists():
            make_real_world_clip(output_path, source_path, start_time)
        created.append(f"{filename} @ {start_time}")
    return f"{note} Generated clips from {source_path.name}: " + ", ".join(created) + "."


def generate_test_clips() -> str:
    clip_builders = {
        "gradient.mkv": make_gradient_clip,
        "detail.mkv": make_detail_clip,
        "motion.mkv": make_motion_clip,
        "bars.mkv": make_bars_clip,
    }
    for filename, builder in clip_builders.items():
        output_path = TEST_CLIPS_DIR / filename
        if not output_path.exists():
            builder(output_path)
    return generate_real_world_clips()


def generate_reference_encodes() -> None:
    for clip_path in list_test_clips():
        clip_name = clip_path.stem
        for profile in PHASE1_PROFILES:
            output_path = reference_path(clip_name, profile)
            if output_path.exists():
                continue
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(clip_path),
                    "-c:v",
                    "prores_videotoolbox",
                    "-profile:v",
                    profile,
                    str(output_path),
                ]
            )


def initialize_results_tsv() -> None:
    maybe_write_text(
        RESULTS_TSV,
        "commit\ttimestamp\tdescription\tssim_avg\tpsnr_avg\tvideo_bytes_ratio_avg\tcomposite_score\tstatus\n",
    )


def write_source_notes(real_world_note: str) -> None:
    content = "\n".join(
        [
            "# Source Notes",
            "",
            "## Verified Upstream Layout",
            "",
            "- Phase 1 patch target is `libavcodec/proresenc_kostya_common.c`.",
            "- FFmpeg `n8.1` stores `prores_quant_matrices`, `prores_mb_limits`, and `prores_profile_info` in that file.",
            "- Proxy already has a separate chroma matrix in current upstream.",
            "- `bits_per_mb` and `mbs_per_slice` are runtime options in `libavcodec/proresenc_kostya.c`, so this harness keeps them as runtime knobs.",
            "- The scan and entropy codebook tables live in `libavcodec/proresdata.c` and are intentionally out of scope for phase 1.",
            "- Current `4444XQ` still points at `QUANT_MAT_HQ` in upstream `n8.1`, so the setup follows source truth rather than the older draft assumption.",
            "",
            "## Test Material",
            "",
            "- The harness uses FFV1-in-Matroska mezzanine clips because the preferred Y4M path was not reliable with Homebrew FFmpeg for 10-bit 4:2:2 round-tripping.",
            "- Synthetic clips: `bars`, `detail`, `gradient`, and `motion`.",
            f"- Real-world clips: {real_world_note}",
            "",
        ]
    )
    write_text(META_DIR / "source_notes.md", content)


def main() -> None:
    ensure_dirs()
    verify_commands()
    ensure_ffmpeg_source()
    snapshot_patch_bases()
    extract_baseline_encoder_params()
    real_world_note = generate_test_clips()
    generate_reference_encodes()
    write_environment_json()
    write_source_notes(real_world_note)
    initialize_results_tsv()
    print("prepare.py completed successfully")


if __name__ == "__main__":
    main()
