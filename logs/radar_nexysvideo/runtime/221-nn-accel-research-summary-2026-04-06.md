# NN accelerator research summary

- Stable baseline confirmed back at `50 MHz`.
- `Configs.scala` local diff for frequency sweep has been cleared.
- Stable `preproc + 50 MHz` bitstream backed up to:
  - `logs/radar_nexysvideo/bit_backups/preproc_50mhz_2026-04-06/`
- New planning document:
  - `docs/radar_nn_accel_three_paths_2026-04-06.md`

## Main output

The document proposes three thesis-capable accelerator directions on top of the current `DDR + AXI DMA + AXI-Stream` SoC baseline:

1. Dense 2D PE-array CNN / BEV backbone accelerator
2. Structured-sparse PE-array accelerator
3. Attention / transformer sub-accelerator

## Recommendation

Recommended path:

1. Build a dense PE-array baseline first
2. Extend it to structured sparsity
3. Keep attention acceleration as a later-stage extension

This ordering best matches the current verified hardware baseline and the FPGA timing ceiling already observed during the 50/60/75 MHz exploration.
