# Source Notes

## Verified Upstream Layout

- Phase 1 patch target is `libavcodec/proresenc_kostya_common.c`.
- FFmpeg `n8.1` stores `prores_quant_matrices`, `prores_mb_limits`, and `prores_profile_info` in that file.
- Proxy already has a separate chroma matrix in current upstream.
- `bits_per_mb` and `mbs_per_slice` are runtime options in `libavcodec/proresenc_kostya.c`, so this harness keeps them as runtime knobs.
- The scan and entropy codebook tables live in `libavcodec/proresdata.c` and are intentionally out of scope for phase 1.
- Current `4444XQ` still points at `QUANT_MAT_HQ` in upstream `n8.1`, so the setup follows source truth rather than the older draft assumption.

## Test Material

- The current setup produced 4 synthetic 1920x1080, 24000/1001, progressive, `yuv422p10le` mezzanine clips: `bars`, `detail`, `gradient`, and `motion`.
- The preferred Y4M path was not reliable with Homebrew FFmpeg for 10-bit 4:2:2 round-tripping, so the harness uses FFV1-in-Matroska mezzanine clips instead.
- Real-world clip download failed during setup, so phase 1 is currently running on synthetic clips only.

## Sanity Checks

- Apple repeatability check on `bars` + `proxy`: byte-identical across two independent `prores_videotoolbox` encodes, SSIM `1.0`, PSNR `inf`, video packet byte ratio `1.0`.
- Apple reference self-check: SSIM `1.0`, PSNR `inf`, video packet byte ratio `1.0`.
- Candidate self-check: SSIM `1.0`, PSNR `inf`, video packet byte ratio `1.0`.
- Cross-encoder sensitivity check on `bars` + `proxy`: SSIM `0.992636`, PSNR `32.608694`, byte ratio `1.045919`, not byte-identical.
- Parameter sensitivity check: changing the first `proxy` luma matrix entry from `4` to `5` moved the global composite score from `0.920007` to `0.920523`, confirming the harness responds to `encoder_params.py`.

## Baseline

- Baseline global summary: SSIM `0.962433`, PSNR `26.4697`, average video bytes ratio `0.969394`, composite `0.920007`.
- The baseline is recorded in `results.tsv`.
