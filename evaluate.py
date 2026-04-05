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
    archived_metrics_path,
    candidate_path,
    composite_score,
    find_command,
    git_short_head,
    latest_incumbent_row,
    list_test_clips,
    load_encoder_params,
    load_phase2_policy,
    overall_score,
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
    case_score = composite_score(ssim_avg, ratio)
    return {
        "ssim_avg": ssim_avg,
        "psnr_avg": psnr_avg,
        "reference_video_packet_bytes": reference_bytes,
        "candidate_video_packet_bytes": candidate_bytes,
        "video_bytes_ratio": ratio,
        "case_score": case_score,
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
            "composite_score": statistics.fmean(item["case_score"] for item in items),
        }
    return {
        "ssim_avg": statistics.fmean(item["ssim_avg"] for item in case_metrics),
        "psnr_avg": statistics.fmean(item["psnr_avg"] for item in case_metrics),
        "video_bytes_ratio_avg": statistics.fmean(item["video_bytes_ratio"] for item in case_metrics),
        "composite_score": statistics.fmean(item["case_score"] for item in case_metrics),
        "per_profile": per_profile,
    }


def holdout_case_deltas(current_cases: list[dict], incumbent_cases: list[dict]) -> tuple[float, dict[str, float]]:
    incumbent_map = {(case["clip"], case["profile"]): case["case_score"] for case in incumbent_cases}
    deltas: dict[str, float] = {}
    worst = 0.0
    for case in current_cases:
        key = (case["clip"], case["profile"])
        if key not in incumbent_map:
            continue
        delta = case["case_score"] - incumbent_map[key]
        deltas[f"{case['clip']}::{case['profile']}"] = delta
        worst = min(worst, delta)
    return worst, deltas


def build_decision(development_cases: list[dict], holdout_cases: list[dict]) -> dict:
    policy = load_phase2_policy()
    development_summary = aggregate(development_cases)
    holdout_summary = aggregate(holdout_cases)
    development_score = development_summary["composite_score"]
    holdout_score = holdout_summary["composite_score"]
    overall = overall_score(development_score, holdout_score)

    incumbent_row = latest_incumbent_row()
    if incumbent_row is None:
        return {
            "development_score": development_score,
            "holdout_score": holdout_score,
            "overall_score": overall,
            "overall_delta": None,
            "holdout_score_delta": None,
            "worst_holdout_case_delta": None,
            "holdout_case_deltas": {},
            "keep_eligible": True,
            "reasons": ["No phase 2 incumbent recorded yet."],
            "incumbent": None,
        }

    metrics_path = archived_metrics_path(str(incumbent_row["commit"]))
    if not metrics_path.exists():
        return {
            "development_score": development_score,
            "holdout_score": holdout_score,
            "overall_score": overall,
            "overall_delta": None,
            "holdout_score_delta": None,
            "worst_holdout_case_delta": None,
            "holdout_case_deltas": {},
            "keep_eligible": False,
            "reasons": [f"Incumbent metrics archive missing: {metrics_path.name}"],
            "incumbent": incumbent_row,
        }

    incumbent_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    incumbent_decision = incumbent_metrics["decision"]
    incumbent_holdout_cases = incumbent_metrics["holdout"]["cases"]
    holdout_worst_delta, holdout_deltas = holdout_case_deltas(holdout_cases, incumbent_holdout_cases)

    overall_delta = overall - incumbent_decision["overall_score"]
    holdout_score_delta = holdout_score - incumbent_decision["holdout_score"]
    gates = policy["GATES"]

    reasons = []
    if overall_delta <= 0:
        reasons.append("Overall score did not improve.")
    if holdout_score_delta < -float(gates["max_holdout_score_drop"]):
        reasons.append("Holdout score dropped past the allowed threshold.")
    if holdout_worst_delta < -float(gates["max_holdout_case_drop"]):
        reasons.append("At least one holdout case regressed past the allowed threshold.")

    return {
        "development_score": development_score,
        "holdout_score": holdout_score,
        "overall_score": overall,
        "overall_delta": overall_delta,
        "holdout_score_delta": holdout_score_delta,
        "worst_holdout_case_delta": holdout_worst_delta,
        "holdout_case_deltas": holdout_deltas,
        "keep_eligible": not reasons,
        "reasons": reasons or ["Eligible keep."],
        "incumbent": {
            "commit": incumbent_row["commit"],
            "description": incumbent_row["description"],
            "overall_score": incumbent_decision["overall_score"],
            "holdout_score": incumbent_decision["holdout_score"],
        },
    }


def evaluate_pack(
    *,
    experiment_dir: Path,
    ffmpeg_bin: Path,
    ffprobe_path: str,
    system_ffmpeg: str,
    params: dict,
    pack: str,
) -> list[dict]:
    cases = []
    for clip_path in list_test_clips(pack):
        clip_name = clip_path.stem
        for profile in PHASE1_PROFILES:
            candidate = candidate_path(experiment_dir, clip_name, profile, pack)
            reference = reference_path(clip_name, profile, pack)
            encode_candidate(ffmpeg_bin, clip_path, profile, candidate, params["RUNTIME_DEFAULTS"])
            metrics = measure_pair(system_ffmpeg, ffprobe_path, reference, candidate)
            metrics.update(
                {
                    "clip": clip_name,
                    "profile": profile,
                    "pack": pack,
                    "candidate_path": str(candidate),
                    "reference_path": str(reference),
                }
            )
            cases.append(metrics)
            print(
                f"CASE pack={pack} clip={clip_name} profile={profile} "
                f"ssim_avg={metrics['ssim_avg']:.6f} psnr_avg={metrics['psnr_avg']:.4f} "
                f"video_bytes_ratio={metrics['video_bytes_ratio']:.6f} case_score={metrics['case_score']:.6f}"
            )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", default=str(EXPERIMENTS_DIR / "current"))
    args = parser.parse_args()

    policy = load_phase2_policy()
    experiment_dir = Path(args.experiment_dir)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = FFMPEG_SOURCE_DIR / "ffmpeg"
    ffprobe_path = find_command("ffprobe")
    system_ffmpeg = find_command("ffmpeg")
    params = load_encoder_params()

    development_cases = evaluate_pack(
        experiment_dir=experiment_dir,
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_path=ffprobe_path,
        system_ffmpeg=system_ffmpeg,
        params=params,
        pack=policy["DEVELOPMENT_PACK"],
    )
    holdout_cases = evaluate_pack(
        experiment_dir=experiment_dir,
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_path=ffprobe_path,
        system_ffmpeg=system_ffmpeg,
        params=params,
        pack=policy["HOLDOUT_PACK"],
    )

    development_summary = aggregate(development_cases)
    holdout_summary = aggregate(holdout_cases)
    decision = build_decision(development_cases, holdout_cases)
    output = {
        "git_head": git_short_head(),
        "score_version": policy["SCORE_VERSION"],
        "development": {
            "cases": development_cases,
            "summary": development_summary,
        },
        "holdout": {
            "cases": holdout_cases,
            "summary": holdout_summary,
        },
        "decision": decision,
    }
    metrics_path = experiment_dir / "metrics.json"
    metrics_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(
        f"DEVELOPMENT composite_score={development_summary['composite_score']:.6f} "
        f"ssim_avg={development_summary['ssim_avg']:.6f} "
        f"video_bytes_ratio_avg={development_summary['video_bytes_ratio_avg']:.6f}"
    )
    print(
        f"HOLDOUT composite_score={holdout_summary['composite_score']:.6f} "
        f"ssim_avg={holdout_summary['ssim_avg']:.6f} "
        f"video_bytes_ratio_avg={holdout_summary['video_bytes_ratio_avg']:.6f}"
    )
    print(
        f"DECISION overall_score={decision['overall_score']:.6f} "
        f"keep_eligible={'yes' if decision['keep_eligible'] else 'no'}"
    )
    print(
        f"FINAL_METRIC overall_score={decision['overall_score']:.6f} "
        f"development_score={decision['development_score']:.6f} "
        f"holdout_score={decision['holdout_score']:.6f} "
        f"keep_eligible={'yes' if decision['keep_eligible'] else 'no'}"
    )


if __name__ == "__main__":
    main()
