# Source Notes

{
  "verified_layout": [
    "Phase 1 patch target is libavcodec/proresenc_kostya_common.c.",
    "Current FFmpeg n8.1 stores prores_quant_matrices, prores_mb_limits, and prores_profile_info in that file.",
    "Proxy already has a separate chroma matrix.",
    "bits_per_mb and mbs_per_slice are runtime options in proresenc_kostya.c and remain runtime knobs here.",
    "The ProRes scan/codebook tables live in libavcodec/proresdata.c and are excluded from phase 1 search.",
    "Current 4444XQ still points at QUANT_MAT_HQ in upstream n8.1, matching source rather than the older draft assumption."
  ],
  "real_world_clip": "No real-world clip downloaded. Network fetch failed."
}
