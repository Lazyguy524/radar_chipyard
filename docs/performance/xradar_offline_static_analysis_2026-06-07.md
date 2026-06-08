# Xradar Offline Static Analysis

Date: 2026-06-07

Scope: offline work that does not require Nexys Video board access. This analysis supports the RISC-V/Xradar direction but does not replace board profiling.

## Work Completed

Added software-golden artifacts:

- `tests/radar_xradar_fallback.h`
- `tests/radar-xradar-fallback-host.c`
- `tests/radar-xradar-static-model-host.c`
- `tests/radar-axi-dma-qmlp-mmio-profile.c`

Added repeatable host test target:

```bash
make -C tests xradar-host-test
make -C tests xradar-static-model
```

The host test validates:

- signed packed int8 lane order for `rqdot4`,
- `rqscale8` ReLU and positive clamp edge cases,
- QMLP golden logits,
- 8 synthetic QMLP cases against scalar C inference,
- static operation counts for the QMLP mapping.

## Host Test Result

Observed output summary:

```text
[XRADAR-FALLBACK] counts rqdot4=848 scalar_tail_macs=64 rqscale8=96 total_macs=3456 packed_mac_coverage_x100=9814
[XRADAR-FALLBACK] PASSED
```

Case logits:

| Case | Label | Logits |
| ---: | --- | --- |
| 0 | `golden_base` | `{855, -10706}` |
| 1 | `zero` | `{861, 508}` |
| 2 | `alternating_perturb` | `{979, -8599}` |
| 3 | `sparse_keep3` | `{291, 151}` |
| 4 | `sign_flip_even` | `{-3940, -5776}` |
| 5 | `half_scale` | `{905, -5277}` |
| 6 | `offset_plus` | `{-490, -9698}` |
| 7 | `offset_minus` | `{-437, 3496}` |

## Static Instruction Opportunity

QMLP MAC count:

| Layer | Shape | MACs | `rqdot4` groups | Scalar tail |
| --- | --- | ---: | ---: | ---: |
| L1 | `64 x 21` | 1344 | 320 | 64 |
| L2 | `32 x 64` | 2048 | 512 | 0 |
| L3 | `2 x 32` | 64 | 16 | 0 |
| Total | - | 3456 | 848 | 64 |

Static packed coverage:

```text
3392 / 3456 = 98.14%
```

Hidden-layer fixed-point scale operations:

```text
L1 64 + L2 32 = 96 rqscale8-equivalent operations
```

This makes `rqdot4` and `rqscale8` plausible first candidates from a static-operation perspective.

Static model target:

```bash
make -C tests xradar-static-model
```

Current model output:

```text
[XRADAR-STATIC] layer=L1 shape=64x21 macs=1344 rqdot4=320 tail_macs=64 scalar_loads=2688 packed_loads=768 packed_load_reduction_x100=7142
[XRADAR-STATIC] layer=L2 shape=32x64 macs=2048 rqdot4=512 tail_macs=0 scalar_loads=4096 packed_loads=1024 packed_load_reduction_x100=7500
[XRADAR-STATIC] layer=L3 shape=2x32 macs=64 rqdot4=16 tail_macs=0 scalar_loads=128 packed_loads=32 packed_load_reduction_x100=7500
[XRADAR-STATIC] total_macs=3456 rqdot4=848 packed_terms=3392 tail_macs=64 packed_coverage_x100=9814 rqscale8=96
```

Finite Amdahl model output:

```text
[XRADAR-AMDAHL] f_pct=20 sk2x_x1000=1111 sk4x_x1000=1176 sk6x_x1000=1200 sk8x_x1000=1212
[XRADAR-AMDAHL] f_pct=40 sk2x_x1000=1250 sk4x_x1000=1429 sk6x_x1000=1500 sk8x_x1000=1538
[XRADAR-AMDAHL] f_pct=50 sk2x_x1000=1333 sk4x_x1000=1600 sk6x_x1000=1714 sk8x_x1000=1778
[XRADAR-AMDAHL] f_pct=60 sk2x_x1000=1429 sk4x_x1000=1818 sk6x_x1000=2000 sk8x_x1000=2105
[XRADAR-AMDAHL] f_pct=70 sk2x_x1000=1538 sk4x_x1000=2105 sk6x_x1000=2400 sk8x_x1000=2581
[XRADAR-AMDAHL] f_pct=80 sk2x_x1000=1667 sk4x_x1000=2500 sk6x_x1000=3000 sk8x_x1000=3333
```

These numbers are reported as `x1000`, so `1429` means approximately `1.429x`.

## MMIO / Polling Instrumentation Wrapper

Added:

- `tests/radar-axi-dma-qmlp-mmio-profile.c`

This is a dedicated profiling wrapper for the `racc.*` gate. It does not modify the shared DMA helpers used by normal validation.

It reports:

- QMLP control cycles,
- DMA setup cycles,
- DMA polling cycles,
- verify cycles,
- hardware kernel cycles,
- MMIO reads per sample,
- MMIO writes per sample,
- QMLP idle polling iterations,
- DMA ready checks,
- DMA running polling iterations,
- DMA done polling iterations.

RISC-V build command:

```bash
source /home/soooarr/anaconda3/etc/profile.d/conda.sh
conda activate /home/soooarr/chipyard/.conda-env
make -C tests -B radar-axi-dma-qmlp-mmio-profile.riscv
```

Build result:

- Passed.
- Bare-metal linker warning observed: `LOAD segment with RWX permissions`.

Size comparison:

```text
text   data  bss   dec    filename
34964  16    0     34980  tests/radar-axi-dma-qmlp-mmio-profile.riscv
34190  16    0     34206  tests/radar-axi-dma-qmlp-profile.riscv
8296   16    8     8320   tests/radar-qmlp-cpu-profile.riscv
```

Archived disassembly:

- `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/phase0-xradar-baseline-gate-2026-06-06/objdump-radar-axi-dma-qmlp-mmio-profile-2026-06-07.txt`

Board command when UART is available:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --bin tests/radar-axi-dma-qmlp-mmio-profile.riscv \
  --log-name phase0-qmlp-mmio-profile-2026-06-07
```

Parse:

- `[QMLP-MMIO-PROFILE] batch=... prep_avg=... qctrl_avg=... dma_setup_avg=... dma_poll_avg=...`
- `[QMLP-MMIO-PROFILE] batch=... mmio_reads_per_sample=... mmio_writes_per_sample=...`

## Current Objdump Evidence

A rebuilt CPU-profile disassembly was archived to:

- `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/phase0-xradar-baseline-gate-2026-06-06/objdump-radar-qmlp-cpu-profile-rebuilt-2026-06-07.txt`

Observed markers include:

- `rdcycle` and `rdinstret` instrumentation in the profile binary.
- multiple scalar `mulw` / `mul` instructions in the QMLP/rounding path.

This is enough to confirm that the current binary contains scalar multiply work and CSR instrumentation, but it is not a dynamic cycle-share measurement.

## What This Proves

- The first `Xradar` arithmetic semantics can be defined bit-exactly against current QMLP software/golden data.
- `rqdot4` maps cleanly to the current QMLP layer dimensions with only a small L1 tail.
- `rqscale8` matches the current QMLP hidden-layer fixed-point activation order.
- The software fallback can serve as a golden reference before any RoCC or Rocket execute-stage RTL exists.
- A dedicated `racc.*` gate wrapper now exists and builds, so future board access can measure MMIO/setup/polling without editing validation helpers.

## What This Does Not Prove

- It does not prove `rqdot4` is at least 40% of CPU-only QMLP cycles.
- It does not prove a RoCC implementation will speed up the workload.
- It does not prove execute-stage timing feasibility at 60 MHz or 75 MHz.
- It does not prove `racc.*` is useful; MMIO/polling instrumentation is still missing.
- It does not answer the Gemmini resource/timing baseline.

## Next Offline Tasks

1. Run `radar-qmlp-cpu-profile.riscv` when board UART is available.
2. Run `radar-axi-dma-qmlp-mmio-profile.riscv` when board UART is available.
3. Add a small pure-C Feature21 helper model if the thesis needs code-size/instruction-count evidence before board access.
4. Prepare a minimal RoCC source skeleton only after the Phase 0 gate explicitly chooses arithmetic custom instructions as the first implementation target.
