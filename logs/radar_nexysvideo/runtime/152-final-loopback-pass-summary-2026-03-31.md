# Final Loopback Pass Summary

Date: 2026-03-31

## Result

`radar-axi-dma-loopback.riscv` passed on hardware after a fresh `CPU_RESET`.

Primary run log:

- `151-run-loopback-after-cpu-reset-cachemaint-2026-03-31.log`

## What changed

Two separate issues were involved:

1. A hardware MM2S response-routing bug caused by AXI ID truncation at the Nexys Video MIG wrapper.
2. A software-visible cache maintenance gap when Rocket and AXI DMA shared cacheable DDR buffers.

The first issue was fixed earlier by correcting the MIG-facing AXI ID budget.
The second issue was resolved by adding cache sweep / eviction steps around the DMA transfer in `tests/radar-axi-dma-loopback.c`.

## Final interpretation

With both fixes in place:

- MM2S and S2MM configuration/startup remain clean
- DMA transfer completes
- software comparison passes
- `uart_tsi` selfcheck also passes on the same run

This means the original MM2S hardware bug is resolved, and the remaining post-fix data mismatch was due to cache coherence handling in the software test.
