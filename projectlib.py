from __future__ import annotations

import importlib.util
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
META_DIR = ROOT / "meta"
PATCH_BASES_DIR = ROOT / "patch_bases"
TEST_CLIPS_DIR = ROOT / "test_clips"
REFERENCE_DIR = ROOT / "reference_encodes"
EXPERIMENTS_DIR = ROOT / "experiments"
FFMPEG_SOURCE_DIR = ROOT / "ffmpeg_source"
RESULTS_TSV = ROOT / "results.tsv"
ENCODER_PARAMS_PATH = ROOT / "encoder_params.py"

FFMPEG_REMOTE = "https://github.com/FFmpeg/FFmpeg.git"
FFMPEG_TAG = "n8.1"
FFMPEG_EXPECTED_COMMIT = "9047fa1b084f76b1b4d065af2d743df1b40dfb56"

PHASE1_PROFILES = ["proxy", "lt", "standard", "hq"]
PROFILE_DISPLAY_NAMES = {
    "proxy": "proxy",
    "lt": "LT",
    "standard": "standard",
    "hq": "high quality",
}
PROFILE_TAGS = {
    "proxy": "MKTAG('a', 'p', 'c', 'o')",
    "lt": "MKTAG('a', 'p', 'c', 's')",
    "standard": "MKTAG('a', 'p', 'c', 'n')",
    "hq": "MKTAG('a', 'p', 'c', 'h')",
}
PROFILE_QUANT_ENUMS = {
    "proxy": ("QUANT_MAT_PROXY", "QUANT_MAT_PROXY_CHROMA"),
    "lt": ("QUANT_MAT_LT", "QUANT_MAT_LT"),
    "standard": ("QUANT_MAT_STANDARD", "QUANT_MAT_STANDARD"),
    "hq": ("QUANT_MAT_HQ", "QUANT_MAT_HQ"),
}

MATRIX_LABELS = [
    "proxy",
    "proxy chromas",
    "LT",
    "standard",
    "high quality",
    "XQ luma",
    "codec default",
]

HOME_BREW_BIN = Path("/opt/homebrew/bin")


class CommandError(RuntimeError):
    pass


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


def ensure_dirs() -> None:
    for path in [META_DIR, PATCH_BASES_DIR, TEST_CLIPS_DIR, REFERENCE_DIR, EXPERIMENTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def candidate_paths() -> dict[str, Path]:
    return {
        "common": FFMPEG_SOURCE_DIR / "libavcodec" / "proresenc_kostya_common.c",
        "kostya": FFMPEG_SOURCE_DIR / "libavcodec" / "proresenc_kostya.c",
        "common_orig": PATCH_BASES_DIR / "proresenc_kostya_common.c.orig",
        "kostya_orig": PATCH_BASES_DIR / "proresenc_kostya.c.orig",
    }


def _default_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts = env.get("PATH", "").split(os.pathsep) if env.get("PATH") else []
    brew_bin = str(HOME_BREW_BIN)
    if brew_bin not in path_parts:
        path_parts.insert(0, brew_bin)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


def run(
    args: list[str] | tuple[str, ...],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = True,
    env: dict[str, str] | None = None,
) -> CommandResult:
    merged_env = _default_env()
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        list(args),
        cwd=cwd or ROOT,
        env=merged_env,
        text=True,
        capture_output=capture_output,
    )
    result = CommandResult(proc.stdout or "", proc.stderr or "", proc.returncode)
    if check and proc.returncode != 0:
        raise CommandError(
            f"Command failed ({proc.returncode}): {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def find_command(name: str) -> str:
    found = shutil.which(name, path=_default_env()["PATH"])
    if found:
        return found
    raise FileNotFoundError(f"Required command not found: {name}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def maybe_write_text(path: Path, content: str) -> None:
    if not path.exists():
        write_text(path, content)


def load_encoder_params() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("encoder_params", ENCODER_PARAMS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {ENCODER_PARAMS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        "PARAM_VERSION": getattr(module, "PARAM_VERSION"),
        "PRORES_MB_LIMITS": getattr(module, "PRORES_MB_LIMITS"),
        "PROFILES": getattr(module, "PROFILES"),
        "RUNTIME_DEFAULTS": getattr(module, "RUNTIME_DEFAULTS"),
    }


def validate_params(data: dict[str, Any]) -> None:
    if data.get("PARAM_VERSION") != 1:
        raise ValueError("PARAM_VERSION must be 1")
    mb_limits = data.get("PRORES_MB_LIMITS")
    if not isinstance(mb_limits, list) or len(mb_limits) != 4 or any(not isinstance(v, int) for v in mb_limits):
        raise ValueError("PRORES_MB_LIMITS must be a list of four integers")
    if any(a >= b for a, b in zip(mb_limits, mb_limits[1:])):
        raise ValueError("PRORES_MB_LIMITS must be strictly ascending")
    profiles = data.get("PROFILES")
    if list(profiles.keys()) != PHASE1_PROFILES:
        raise ValueError(f"PROFILES must contain exactly {PHASE1_PROFILES} in order")
    for name, config in profiles.items():
        for matrix_key in ["luma_matrix", "chroma_matrix"]:
            matrix = config.get(matrix_key)
            if not isinstance(matrix, list) or len(matrix) != 64 or any(not isinstance(v, int) for v in matrix):
                raise ValueError(f"{name}.{matrix_key} must be a 64-element integer list")
        for field in ["min_quant", "max_quant"]:
            if not isinstance(config.get(field), int):
                raise ValueError(f"{name}.{field} must be an integer")
        if config["min_quant"] > config["max_quant"]:
            raise ValueError(f"{name}.min_quant must be <= max_quant")
        br_tab = config.get("br_tab")
        if not isinstance(br_tab, list) or len(br_tab) != 4 or any(not isinstance(v, int) for v in br_tab):
            raise ValueError(f"{name}.br_tab must be a 4-element integer list")
    runtime_defaults = data.get("RUNTIME_DEFAULTS")
    mbs_per_slice = runtime_defaults.get("mbs_per_slice")
    if mbs_per_slice not in {1, 2, 4, 8}:
        raise ValueError("RUNTIME_DEFAULTS['mbs_per_slice'] must be one of 1, 2, 4, 8")
    bits_per_mb_override = runtime_defaults.get("bits_per_mb_override")
    if bits_per_mb_override is not None and not isinstance(bits_per_mb_override, int):
        raise ValueError("RUNTIME_DEFAULTS['bits_per_mb_override'] must be an integer or None")


def _extract_initializer(text: str, declaration: str) -> str:
    start = text.index(declaration)
    brace_start = text.index("{", start)
    depth = 0
    for idx in range(brace_start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = text.index(";", idx) + 1
                return text[start:end]
    raise ValueError(f"Unable to extract initializer for {declaration}")


def _top_level_groups(block: str) -> list[str]:
    groups: list[str] = []
    outer_start = block.index("{")
    depth = 0
    group_start: int | None = None
    for idx in range(outer_start, len(block)):
        char = block[idx]
        if char == "{":
            depth += 1
            if depth == 2:
                group_start = idx
        elif char == "}":
            if depth == 2 and group_start is not None:
                groups.append(block[group_start : idx + 1])
                group_start = None
            depth -= 1
    return groups


def _ints_from_text(text: str) -> list[int]:
    return [int(match) for match in re.findall(r"-?\d+", text)]


def _assignment_value(group: str, field_name: str) -> str | None:
    prefix = f".{field_name}"
    for raw_line in group.splitlines():
        line = raw_line.strip()
        if not line.startswith(prefix):
            continue
        _, rhs = line.split("=", 1)
        rhs = rhs.strip()
        if "/*" in rhs:
            rhs = rhs.split("/*", 1)[0].rstrip()
        if rhs.endswith(","):
            rhs = rhs[:-1].rstrip()
        return rhs
    return None


def parse_source_baseline(common_c_text: str) -> dict[str, Any]:
    matrices_block = _extract_initializer(common_c_text, "static const uint8_t prores_quant_matrices[][64] =")
    mb_limits_block = _extract_initializer(common_c_text, "static const int prores_mb_limits[NUM_MB_LIMITS] =")
    profiles_block = _extract_initializer(common_c_text, "static const prores_profile prores_profile_info[6] =")

    matrix_groups = _top_level_groups(matrices_block)
    if len(matrix_groups) != 7:
        raise ValueError(f"Expected 7 quant matrices, found {len(matrix_groups)}")
    matrices = [_ints_from_text(group) for group in matrix_groups]
    if any(len(matrix) != 64 for matrix in matrices):
        raise ValueError("Every quant matrix must have 64 elements")

    profile_groups = _top_level_groups(profiles_block)
    if len(profile_groups) != 6:
        raise ValueError(f"Expected 6 profile entries, found {len(profile_groups)}")

    parsed_profiles = []
    for group in profile_groups:
        full_name_match = re.search(r'\.full_name\s*=\s*"([^"]+)"', group)
        min_quant_match = re.search(r"\.min_quant\s*=\s*(\d+)", group)
        max_quant_match = re.search(r"\.max_quant\s*=\s*(\d+)", group)
        br_tab_match = re.search(r"\.br_tab\s*=\s*\{([^}]+)\}", group, re.DOTALL)
        tag_expr = _assignment_value(group, "tag")
        quant_expr = _assignment_value(group, "quant")
        quant_chroma_expr = _assignment_value(group, "quant_chroma")
        if not all(
            [
                full_name_match,
                min_quant_match,
                max_quant_match,
                br_tab_match,
                tag_expr,
                quant_expr,
                quant_chroma_expr,
            ]
        ):
            raise ValueError(f"Unable to parse profile entry:\n{group}")
        parsed_profiles.append(
            {
                "full_name": full_name_match.group(1),
                "tag_expr": str(tag_expr).strip(),
                "min_quant": int(min_quant_match.group(1)),
                "max_quant": int(max_quant_match.group(1)),
                "br_tab": _ints_from_text(br_tab_match.group(1)),
                "quant": str(quant_expr).strip(),
                "quant_chroma": str(quant_chroma_expr).strip(),
            }
        )

    baseline_profiles = {
        "proxy": {
            "luma_matrix": matrices[0],
            "chroma_matrix": matrices[1],
            "min_quant": parsed_profiles[0]["min_quant"],
            "max_quant": parsed_profiles[0]["max_quant"],
            "br_tab": parsed_profiles[0]["br_tab"],
        },
        "lt": {
            "luma_matrix": matrices[2],
            "chroma_matrix": matrices[2],
            "min_quant": parsed_profiles[1]["min_quant"],
            "max_quant": parsed_profiles[1]["max_quant"],
            "br_tab": parsed_profiles[1]["br_tab"],
        },
        "standard": {
            "luma_matrix": matrices[3],
            "chroma_matrix": matrices[3],
            "min_quant": parsed_profiles[2]["min_quant"],
            "max_quant": parsed_profiles[2]["max_quant"],
            "br_tab": parsed_profiles[2]["br_tab"],
        },
        "hq": {
            "luma_matrix": matrices[4],
            "chroma_matrix": matrices[4],
            "min_quant": parsed_profiles[3]["min_quant"],
            "max_quant": parsed_profiles[3]["max_quant"],
            "br_tab": parsed_profiles[3]["br_tab"],
        },
    }

    return {
        "matrices": matrices,
        "mb_limits": _ints_from_text(mb_limits_block),
        "profiles_all": parsed_profiles,
        "baseline_encoder_params": {
            "PARAM_VERSION": 1,
            "PRORES_MB_LIMITS": _ints_from_text(mb_limits_block),
            "PROFILES": baseline_profiles,
            "RUNTIME_DEFAULTS": {
                "mbs_per_slice": 8,
                "bits_per_mb_override": None,
            },
        },
    }


def _format_python_list(values: list[int], indent: int = 8, width: int = 8) -> str:
    chunks = []
    pad = " " * indent
    for offset in range(0, len(values), width):
        row = ", ".join(f"{value}" for value in values[offset : offset + width])
        chunks.append(f"{pad}{row},")
    return "\n".join(chunks)


def render_encoder_params(data: dict[str, Any]) -> str:
    validate_params(data)
    lines = [
        "PARAM_VERSION = 1",
        "",
        f"PRORES_MB_LIMITS = {data['PRORES_MB_LIMITS']}",
        "",
        "PROFILES = {",
    ]
    for profile_name in PHASE1_PROFILES:
        profile = data["PROFILES"][profile_name]
        lines.extend(
            [
                f'    "{profile_name}": {{',
                "        \"luma_matrix\": [",
                _format_python_list(profile["luma_matrix"], indent=12),
                "        ],",
                "        \"chroma_matrix\": [",
                _format_python_list(profile["chroma_matrix"], indent=12),
                "        ],",
                f'        "min_quant": {profile["min_quant"]},',
                f'        "max_quant": {profile["max_quant"]},',
                f'        "br_tab": {profile["br_tab"]},',
                "    },",
            ]
        )
    lines.extend(
        [
            "}",
            "",
            "RUNTIME_DEFAULTS = {",
            f'    "mbs_per_slice": {data["RUNTIME_DEFAULTS"]["mbs_per_slice"]},',
            f'    "bits_per_mb_override": {data["RUNTIME_DEFAULTS"]["bits_per_mb_override"]!r},',
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def _render_c_matrix(matrix: list[int], label: str) -> str:
    rows = []
    for offset in range(0, 64, 8):
        row = ", ".join(f"{value:>2}" for value in matrix[offset : offset + 8])
        rows.append(f"        {row},")
    return "{ // " + label + "\n" + "\n".join(rows) + "\n    }"


def _render_c_profiles(params: dict[str, Any], base_profiles: list[dict[str, Any]]) -> str:
    rendered = []
    for idx, base_profile in enumerate(base_profiles):
        if idx < 4:
            phase_name = PHASE1_PROFILES[idx]
            current = params["PROFILES"][phase_name]
            full_name = PROFILE_DISPLAY_NAMES[phase_name]
            tag_expr = PROFILE_TAGS[phase_name]
            quant_expr, quant_chroma_expr = PROFILE_QUANT_ENUMS[phase_name]
            min_quant = current["min_quant"]
            max_quant = current["max_quant"]
            br_tab = current["br_tab"]
        else:
            full_name = base_profile["full_name"]
            tag_expr = base_profile["tag_expr"]
            quant_expr = base_profile["quant"]
            quant_chroma_expr = base_profile["quant_chroma"]
            min_quant = base_profile["min_quant"]
            max_quant = base_profile["max_quant"]
            br_tab = base_profile["br_tab"]

        rendered.append(
            "\n".join(
                [
                    "    {",
                    f'        .full_name = "{full_name}",',
                    f"        .tag       = {tag_expr},",
                    f"        .min_quant = {min_quant},",
                    f"        .max_quant = {max_quant},",
                    f"        .br_tab    = {{ {', '.join(str(v) for v in br_tab)} }},",
                    f"        .quant     = {quant_expr},",
                    f"        .quant_chroma = {quant_chroma_expr},",
                    "    }",
                ]
            )
        )
    return ",\n".join(rendered)


def patch_common_source(base_text: str, params: dict[str, Any], baseline: dict[str, Any]) -> str:
    validate_params(params)

    matrices = list(baseline["matrices"])
    matrices[0] = params["PROFILES"]["proxy"]["luma_matrix"]
    matrices[1] = params["PROFILES"]["proxy"]["chroma_matrix"]
    matrices[2] = params["PROFILES"]["lt"]["luma_matrix"]
    matrices[3] = params["PROFILES"]["standard"]["luma_matrix"]
    matrices[4] = params["PROFILES"]["hq"]["luma_matrix"]

    quant_block = "static const uint8_t prores_quant_matrices[][64] = {\n"
    quant_block += ",\n".join(_render_c_matrix(matrix, label) for matrix, label in zip(matrices, MATRIX_LABELS))
    quant_block += "\n};"

    mb_limits_block = "static const int prores_mb_limits[NUM_MB_LIMITS] = {\n"
    for value, comment in zip(
        params["PRORES_MB_LIMITS"],
        [
            "up to 720x576",
            "up to 960x720",
            "up to 1440x1080",
            "up to 2048x1152",
        ],
    ):
        mb_limits_block += f"    {value}, // {comment}\n"
    mb_limits_block += "};"

    profiles_block = "static const prores_profile prores_profile_info[6] = {\n"
    profiles_block += _render_c_profiles(params, baseline["profiles_all"])
    profiles_block += "\n};"

    updated = re.sub(
        r"static const uint8_t prores_quant_matrices\[\]\[64\] = \{.*?\n\};",
        quant_block,
        base_text,
        count=1,
        flags=re.DOTALL,
    )
    updated = re.sub(
        r"static const int prores_mb_limits\[NUM_MB_LIMITS\] = \{.*?\n\};",
        mb_limits_block,
        updated,
        count=1,
        flags=re.DOTALL,
    )
    updated = re.sub(
        r"static const prores_profile prores_profile_info\[6\] = \{.*?\n\};",
        profiles_block,
        updated,
        count=1,
        flags=re.DOTALL,
    )
    return updated


def write_environment_json() -> None:
    env = {
        "generated_at": now_iso(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version,
        },
        "commands": {},
    }
    for command in ["ffmpeg", "ffprobe", "git", "python3", "clang", "make"]:
        resolved = find_command(command)
        version_args = {
            "ffmpeg": [resolved, "-version"],
            "ffprobe": [resolved, "-version"],
            "git": [resolved, "--version"],
            "python3": [resolved, "--version"],
            "clang": [resolved, "--version"],
            "make": [resolved, "--version"],
        }[command]
        result = run(version_args, check=True)
        env["commands"][command] = {
            "path": resolved,
            "version": (result.stdout or result.stderr).splitlines()[0],
        }
    write_text(META_DIR / "environment.json", json.dumps(env, indent=2) + "\n")


def list_test_clips() -> list[Path]:
    return sorted(TEST_CLIPS_DIR.glob("*.mkv"))


def reference_path(clip_name: str, profile: str) -> Path:
    return REFERENCE_DIR / f"{clip_name}_{profile}_apple.mov"


def candidate_path(experiment_dir: Path, clip_name: str, profile: str) -> Path:
    return experiment_dir / "candidates" / f"{clip_name}_{profile}_candidate.mov"


def video_packet_bytes(path: Path, ffprobe_path: str) -> int:
    result = run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=size",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ]
    )
    total = 0
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped:
            total += int(stripped)
    return total


def parse_ssim(stderr: str) -> float:
    match = re.search(r"All:([0-9.]+)", stderr)
    if not match:
        raise ValueError(f"Unable to parse SSIM output:\n{stderr}")
    return float(match.group(1))


def parse_psnr(stderr: str) -> float:
    match = re.search(r"average:([0-9.]+)", stderr)
    if not match:
        raise ValueError(f"Unable to parse PSNR output:\n{stderr}")
    return float(match.group(1))


def composite_score(ssim_avg: float, video_bytes_ratio: float) -> float:
    rate_term = max(0.0, 1.0 - 0.20 * abs(math.log2(video_bytes_ratio)))
    return ssim_avg * rate_term


def git_short_head() -> str:
    try:
        return run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).stdout.strip()
    except Exception:
        return "nogit"
