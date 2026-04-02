# Preproc hardware test summary

- Test binary: `tests/radar-axi-dma-preproc.riscv`
- Run log: `212-run-dma-preproc-after-cpu-reset-2026-04-01.log`
- Result: `PASSED`

## Confirmed points
- Boot-time preprocessor CSR page is readable.
- `ADD32` mode passed.
- `RELU16` mode passed.
- Both modes reported `in=32`, `out=32`, `frames=1`.
- Capability register reported `0x1f`.

## Key interpretation
- The new local CSR page at `0x6000_0200+` is alive on hardware.
- The `MM2S -> RadarAXISPreprocessor -> S2MM` data path is working on board.
- Existing DMA regression had already passed on the same bitstream in `209-run-integrated-regression-on-preproc-bitstream-2026-04-01.log`.
