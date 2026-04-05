# Source Notes

## Verified Upstream Layout

- Phase 1 patch target is `libavcodec/proresenc_kostya_common.c`.
- FFmpeg `n8.1` stores `prores_quant_matrices`, `prores_mb_limits`, and `prores_profile_info` in that file.
- Proxy already has a separate chroma matrix in current upstream.
- `bits_per_mb` and `mbs_per_slice` are runtime options in `libavcodec/proresenc_kostya.c`, so this harness keeps them as runtime knobs.
- The scan and entropy codebook tables live in `libavcodec/proresdata.c` and are intentionally out of scope for phase 1.
- Current `4444XQ` still points at `QUANT_MAT_HQ` in upstream `n8.1`, so the setup follows source truth rather than the older draft assumption.

## Test Material

- The harness uses FFV1-in-Matroska mezzanine clips because the preferred Y4M path was not reliable with Homebrew FFmpeg for 10-bit 4:2:2 round-tripping.
- Synthetic clips: `bars`, `detail`, `gradient`, and `motion`.
- Real-world clips: Blender Foundation Tears of Steel sample, CC BY 3.0. Generated clips from tears_of_steel_1080p.mov: realworld_tos_dialogue.mkv @ 00:02:10.0, realworld_tos_action.mkv @ 00:07:18.0.
