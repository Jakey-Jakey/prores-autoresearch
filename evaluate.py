#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from projectlib import (
    EXPERIMENTS_DIR,
    FFMPEG_SOURCE_DIR,
    PHASE1_PROFILES,
    candidate_path,
    composite_score,
    find_command,
    git_short_head,
    list_test_clips,
    load_encoder_params,
    parse_psnr,
    parse_ssim,
    reference_path,
    run,
    video_packet_bytes,
)


def encode_candidate(ffmpeg_bin: Path, clip_path: Path, profile: str, output_path: Path, runtime_defaults: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(ffmpeg_bin),
        "-y",
        "-i",
        str(clip_path),
        "-c:v",
        "prores_ks",
        "-profile:v",
        profile,
        "-pix_fmt",
        "yuv422p10le",
        "-mbs_per_slice",
        str(runtime_defaults["mbs_per_slice"]),
    ]
    if runtime_defaults["bits_per_mb_override"] is not None:
        command.extend(["-bits_per_mb", str(runtime_defaults["bits_per_mb_override"])])
    command.append(str(output_path))
    run(command)


def measure_pair(ffmpeg_path: str, ffprobe_path: str, ref_path: Path, candidate: Path) -> dict:
    ssim_result = run(
        [ffmpeg_path, "-i", str(ref_path), "-i", str(candidate), "-lavfi", "[0:v][1:v]ssim", "-f", "null", "-"]
    )
    psnr_result = run(
        [ffmpeg_path, "-i", str(ref_path), "-i", str(candidate), "-lavfi", "[0:v][1:v]psnr", "-f", "null", "-"]
    )
    reference_bytes = video_packet_bytes(ref_path, ffprobe_path)
    candidate_bytes = video_packet_bytes(candidate, ffprobe_path)
    ratio = candidate_bytes / reference_bytes
    ssim_avg = parse_ssim(ssim_result.stderr)
    psnr_avg = parse_psnr(psnr_result.stderr)
    return {
        "ssim_avg": ssim_avg,
        "psnr_avg": psnr_avg,
        "reference_video_packet_bytes": reference_bytes,
        "candidate_video_packet_bytes": candidate_bytes,
        "video_bytes_ratio": ratio,
        "composite": composite_score(ssim_avg, ratio),
    }


def aggregate(case_metrics: list[dict]) -> dict:
    profile_groups: dict[str, list[dict]] = defaultdict(list)
    for case in case_metrics:
        profile_groups[case["profile"]].append(case)
    per_profile = {}
    for profile, items in profile_groups.items():
        per_profile[profile] = {
            "ssim_avg": statistics.fmean(item["ssim_avg"] for item in items),
            "psnr_avg": statistics.fmean(item["psnr_avg"] for item in items),
            "video_bytes_ratio_avg": statistics.fmean(item["video_bytes_ratio"] for item in items),
            "composite_score": statistics.fmean(item["composite"] for item in items),
        }
    return {
        "ssim_avg": statistics.fmean(item["ssim_avg"] for item in case_metrics),
        "psnr_avg": statistics.fmean(item["psnr_avg"] for item in case_metrics),
        "video_bytes_ratio_avg": statistics.fmean(item["video_bytes_ratio"] for item in case_metrics),
        "composite_score": statistics.fmean(item["composite"] for item in case_metrics),
        "per_profile": per_profile,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", default=str(EXPERIMENTS_DIR / "current"))
    args = parser.parse_args()

    experiment_dir = Path(args.experiment_dir)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = FFMPEG_SOURCE_DIR / "ffmpeg"
    ffprobe_path = find_command("ffprobe")
    system_ffmpeg = find_command("ffmpeg")
    params = load_encoder_params()

    cases = []
    for clip_path in list_test_clips():
        clip_name = clip_path.stem
        for profile in PHASE1_PROFILES:
            candidate = candidate_path(experiment_dir, clip_name, profile)
            reference = reference_path(clip_name, profile)
            encode_candidate(ffmpeg_bin, clip_path, profile, candidate, params["RUNTIME_DEFAULTS"])
            metrics = measure_pair(system_ffmpeg, ffprobe_path, reference, candidate)
            metrics.update(
                {
                    "clip": clip_name,
                    "profile": profile,
                    "candidate_path": str(candidate),
                    "reference_path": str(reference),
                }
            )
            cases.append(metrics)
            print(
                f"CASE clip={clip_name} profile={profile} "
                f"ssim_avg={metrics['ssim_avg']:.6f} psnr_avg={metrics['psnr_avg']:.4f} "
                f"video_bytes_ratio={metrics['video_bytes_ratio']:.6f} composite={metrics['composite']:.6f}"
            )

    summary = aggregate(cases)
    output = {
        "git_head": git_short_head(),
        "cases": cases,
        "summary": summary,
    }
    metrics_path = experiment_dir / "metrics.json"
    metrics_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(
        f"SUMMARY ssim_avg={summary['ssim_avg']:.6f} psnr_avg={summary['psnr_avg']:.4f} "
        f"video_bytes_ratio_avg={summary['video_bytes_ratio_avg']:.6f} composite_score={summary['composite_score']:.6f}"
    )
    print(
        f"FINAL_METRIC composite_score={summary['composite_score']:.6f} "
        f"ssim_avg={summary['ssim_avg']:.6f} psnr_avg={summary['psnr_avg']:.4f} "
        f"video_bytes_ratio_avg={summary['video_bytes_ratio_avg']:.6f}"
    )


if __name__ == "__main__":
    main()
