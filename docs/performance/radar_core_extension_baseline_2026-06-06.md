# RISC-V Core / Xradar Phase 0 Baseline Gate

Date: 2026-06-06

Scope: Phase 0 baseline and design-space triage for RISC-V core / Xradar / Feature21 + QMLP. This is a go/no-go gate, not an implementation phase.

## Guardrails And Backup

- Initial worktree state was checked with `git status --short`.
- Tracked changes were backed up to:
  - `docs/backups/phase0_before_xradar_20260606_154834.patch`
- Dirty `generators/testchipip` submodule changes were backed up separately:
  - `docs/backups/phase0_before_xradar_20260606_154834_generators_testchipip.patch`
- Important untracked docs/code were archived to:
  - `docs/backups/phase0_before_xradar_20260606_154834_untracked_important.tar.gz`
- Full untracked and important-untracked lists:
  - `docs/backups/phase0_before_xradar_20260606_154834_untracked_files.txt`
  - `docs/backups/phase0_before_xradar_20260606_154834_untracked_important_files.txt`
- No reset, checkout, or destructive cleanup command was used.

## Evidence Artifacts Created This Step

Runtime workspace:

- `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/phase0-xradar-baseline-gate-2026-06-06/`

Key files:

- `build-phase0-benchmarks-2026-06-06.log`
- `size-phase0-benchmarks-2026-06-06.txt`
- `objdump-radar-qmlp-cpu-only-2026-06-06.txt`
- `objdump-radar-qmlp-cpu-only-hotspots-2026-06-06.txt`
- `build-radar-qmlp-cpu-profile-2026-06-06.log`
- `size-radar-qmlp-cpu-profile-2026-06-06.txt`
- `objdump-radar-qmlp-cpu-profile-2026-06-06.txt`
- `qmlp-gemmini-utilization-estimate-2026-06-06.txt`
- `timing-util-evidence-2026-06-06.txt`

New source added for Phase 0 measurement:

- `tests/radar-qmlp-cpu-profile.c`

This source builds a standalone profiled CPU-only QMLP ELF without modifying the already-dirty `tests/Makefile`.

## Workload Shape

QMLP dimensions:

| Layer | M for batch=1 | K | N | MACs |
|---|---:|---:|---:|---:|
| L1 | 1 | 21 | 64 | 1344 |
| L2 | 1 | 64 | 32 | 2048 |
| L3 | 1 | 32 | 2 | 64 |
| Total | 1 | - | - | 3456 |

Existing validation/profile batch sizes include `batch=1`, `batch=8`, and larger streaming batches up to `batch=511` under the current 14-bit DMA length limit.

## Current Baseline Matrix

| Baseline | Current evidence | Status |
|---|---|---|
| CPU-only QMLP cycles | Historical board result: `avg_cycles=165343`, `min=165204`, `max=165500` for pure `radar_qmlp_software_infer()` at 50 MHz. | Available as total cycles only. |
| CPU-only QMLP cycle share | New `tests/radar-qmlp-cpu-profile.c` built; it reports dot/MAC upper-bound, quant/relu, residual/control, and `rdinstret`. | Needs board run; no `/dev/ttyUSB*` or `/dev/ttyACM*` present in this step. |
| Feature21 scalar/software-visible cycles | No CPU scalar Feature21 profile found. Hardware Feature21 v1.4a board dump reports `397` cycles avg, min `387`, max `589` for 1000 samples. | CPU scalar baseline missing. |
| Current MMIO/DMA QMLP cycles | Existing no-reset profile: `batch=1` has `prep=1148`, `ctrl=60`, `dma=1622`, `verify=247`, `hw=1301` cycles/sample. `batch=511` has `prep=1142`, `ctrl=0`, `dma=1306`, `verify=88`, `hw=1301`. | Available, but DMA setup/polling is not yet split inside `dma_avg`. |
| Feature21 + QMLP chain cycles | Bypass preproc-chain validation: `large_golden` chain `hw=1301`, `e2e=1121914` cycles/sample; boundary `hw=1301`, `e2e=8977680`. This is bypass-chain, not full Feature21 raw-point hardware. | Partial; full Feature21+QMLP hardware chain cycle baseline still missing. |
| MMIO read/write count | Static wrapper inspection gives lower bounds, but no measured counters. Existing helpers do not count MMIO or polling iterations. | Missing measured count. |
| Instruction count / code size | `radar-qmlp-cpu-only.riscv`: `text=8528`, `data=16`, `bss=8`. `radar-qmlp-cpu-profile.riscv`: `text=8296`, `data=16`, `bss=8`. Static `radar_qmlp_software_infer` disassembly has 137 instructions, including 6 static multiply instructions. | Code size available; dynamic `instret` needs board run. |
| Gemmini feasibility | Local `RadarNexysVideoConfig` includes `gemmini.LeanGemminiConfig`; generated `Gemmini.sv` exists; old `fpga/deliverables/v1_rocket_gemmini/NexysVideoHarness.bit` exists. No matching Gemmini timing/utilization report was found. | Config feasibility partial; resource/timing baseline missing. |

## Existing QMLP DMA Profile Detail

Source evidence: `docs/performance/radar_qmlp_dma_profile_2026-04-16.md` and board log `logs/radar_nexysvideo/runtime/598-qmlp-profile-after-clean-reset-2026-04-16-2026-04-16-212759.log`.

| batch | samples | prep_avg | ctrl_avg | dma_avg | verify_avg | hw_avg |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1000 | 1148 | 60 | 1622 | 247 | 1301 |
| 8 | 1000 | 1142 | 7 | 1345 | 107 | 1301 |
| 32 | 1000 | 1142 | 2 | 1315 | 92 | 1301 |
| 64 | 1000 | 1142 | 1 | 1311 | 90 | 1301 |
| 256 | 1000 | 1142 | 0 | 1307 | 88 | 1301 |
| 511 | 1000 | 1142 | 0 | 1306 | 88 | 1301 |

Important interpretation:

- `ctrl_avg` currently means QMLP idle/clear/enable control only.
- `dma_avg` includes DMA register programming and MM2S/S2MM polling, so it must be split before the `racc.*` gate can be claimed either way.
- Existing data already shows large-batch QMLP DMA is near the hardware kernel limit: `1306` vs `1301` cycles/sample at `batch=511`.

## Current Resource And Timing Context

Current promoted 75 MHz Feature21 + QMLP config:

- Timing report: `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarAXIMMIONexysVideo75MHzConfig/obj/report/timing.txt`
- Bitstream SHA256: `530cceaee2e9d433b5829d32340012fd1ee107c9b16adc4115013f6e2f8cb665`
- Timing SHA256: `d5a81563a12c8977e60584621f7ccd4cc946293de1f5e46e5ef4b0023aea9482`
- WNS `+0.040 ns`, TNS `0.000 ns`, WHS `+0.017 ns`.
- Worst final path is Rocket frontend/icache/fetch queue into Rocket execute decode, not QMLP, ordinary Feature21 quant/writeback, or TSI.

Top hierarchical utilization for the 75 MHz radar config:

| Instance | LUTs | FFs | RAMB36 | RAMB18 | DSP |
|---|---:|---:|---:|---:|---:|
| `NexysVideoHarness` | 29815 | 19222 | 2 | 14 | 12 |
| `radarDMA` | 7703 | 5501 | 2 | 2 | 2 |
| `feature21` | 2470 | 1210 | 0 | 0 | 2 |
| `qmlp` | 2468 | 1580 | 0 | 0 | 0 |

## Gemmini / LeanGemmini Evidence

Local config evidence:

- `fpga/src/main/scala/nexysvideo/Configs.scala` defines `RadarNexysVideoConfig` with `new gemmini.LeanGemminiConfig`.
- `generators/chipyard/src/main/scala/config/RoCCAcceleratorConfigs.scala` defines `LeanGemminiRocketConfig`.
- `generators/gemmini/src/main/scala/gemmini/Configs.scala` defines default/lean Gemmini config with int8 input, int32 accumulator, `tileRows=1`, `tileColumns=1`, `meshRows=16`, `meshColumns=16`, 256 PEs, `sp_capacity=256 KiB`, `acc_capacity=64 KiB`, `dma_buswidth=128`.
- Generated Gemmini collateral exists:
  - `fpga/generated-src/chipyard.fpga.nexysvideo.NexysVideoHarness.RadarNexysVideoConfig/gen-collateral/Gemmini.sv`
  - size `317356` bytes, mtime `2025-11-27`.
- Old Gemmini deliverable bitstream exists:
  - `fpga/deliverables/v1_rocket_gemmini/NexysVideoHarness.bit`
  - SHA256 `103fdff7e4765b4b4b02513ca08f27261dbae59fdb70dc9e771758ea0ba76023`

Missing Gemmini evidence:

- No local `RadarNexysVideoConfig/obj/report/utilization.txt` was found.
- No local `RadarNexysVideoConfig/obj/report/timing.txt` was found.
- Therefore Phase 0 cannot yet claim LeanGemmini is too large, timing-infeasible, or competitive on this Artix-7 target.

Systolic-array utilization estimate against the 16x16 Gemmini block:

| batch | layer | useful MACs | padded MAC slots | PE/tile utilization |
|---:|---|---:|---:|---:|
| 1 | L1 1x21x64 | 1344 | 32768 | 4.10% |
| 1 | L2 1x64x32 | 2048 | 32768 | 6.25% |
| 1 | L3 1x32x2 | 64 | 8192 | 0.78% |
| 1 | total | 3456 | 73728 | 4.69% |
| 8 | L1 8x21x64 | 10752 | 32768 | 32.81% |
| 8 | L2 8x64x32 | 16384 | 32768 | 50.00% |
| 8 | L3 8x32x2 | 512 | 8192 | 6.25% |
| 8 | total | 27648 | 73728 | 37.50% |

Interpretation:

- The QMLP GEMM shapes are small and skinny for a 16x16 systolic endpoint, especially at `batch=1`.
- This is workload-shape evidence only. It does not replace real Gemmini resource/timing/software-overhead measurement.
- To support a thesis claim, Phase 0 still needs either a LeanGemmini NexysVideo implementation report or a documented reason that building it is impractical in this workspace.

## Finite Amdahl Model

All whole-QMLP projections must use:

```text
Speedup_total = 1 / ((1 - f) + f / s_k)
```

Phase 0 measures only `f`. Phase 2/3 must measure finite kernel-local speedup `s_k`. Do not use `1 / (1 - f)` as a realistic expected speedup; that is only the unreachable limit as `s_k -> infinity`.

Sensitivity table:

| f | s_k=2x | s_k=4x | s_k=6x | s_k=8x |
|---:|---:|---:|---:|---:|
| 20% | 1.111x | 1.176x | 1.200x | 1.212x |
| 40% | 1.250x | 1.429x | 1.500x | 1.538x |
| 50% | 1.333x | 1.600x | 1.714x | 1.778x |
| 60% | 1.429x | 1.818x | 2.000x | 2.105x |
| 70% | 1.538x | 2.105x | 2.400x | 2.581x |
| 80% | 1.667x | 2.500x | 3.000x | 3.333x |

## Gate Status After First Step

| Gate | Requirement | Current status |
|---|---|---|
| `rqdot4` | Dot/MAC >= 40% of CPU-only QMLP cycles, or explicit instruction-count/code-size justification. | Not decided. Existing CPU-only total cycles are available, but dot/MAC share is not. New profiled ELF was built and must be run on board. |
| `racc.*` | For named small batch, at least `batch=1`, MMIO/setup/polling >= 20% of accelerator E2E cycles. | Not passed yet. Existing `ctrl_avg=60` cycles/sample is far below 20%, but DMA setup/polling is buried inside `dma_avg`, so a measured MMIO/poll split is still needed before final no-go. |
| quantize/round/clamp or table/index helper | If activation/lookup/control/quantization dominates instead of dot/MAC, pivot first custom arithmetic instruction to that bottleneck. | Pending CPU profile run. |
| Gemmini | Must be treated as dense-GEMM design-space point, with config/resource/timing/workload evidence. | Partial. Config and workload-shape evidence available; resource/timing report missing. |

## Immediate Next Commands

When a board UART is available:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --bin tests/radar-qmlp-cpu-profile.riscv \
  --log-name phase0-radar-qmlp-cpu-profile-2026-06-06
```

Then parse:

- `[CPU-QMLP-PROFILE] summary`
- `[CPU-QMLP-PROFILE] share dot_mac_upper`
- `[CPU-QMLP-PROFILE] share quant_relu`
- `[CPU-QMLP-PROFILE] share control_resid`

Next instrumentation target:

- Add measured MMIO read/write counters and polling-iteration counters to a dedicated Phase 0 wrapper or compile-time profile mode, preferably without changing common helper behavior for normal validation.

Next Gemmini target if implementation time is acceptable:

- Run a LeanGemmini NexysVideo elaboration/implementation evidence pass or recover the missing timing/utilization reports for the existing `RadarNexysVideoConfig` generated collateral.

## Checkpoint 2026-06-07 RISC-V Work Start

The RISC-V/Xradar work is starting from Phase 0 measurement closure, not from immediate RoCC or Rocket RTL edits.

Local status:

- No board UART device was visible under `/dev/ttyUSB*` or `/dev/ttyACM*` during this checkpoint.
- `tests/radar-qmlp-cpu-profile.c` and an existing `tests/radar-qmlp-cpu-profile.riscv` were present, but `tests/Makefile` did not expose this profile target.
- `tests/Makefile` was updated to add:
  - `radar-qmlp-cpu-profile` in `PROGRAMS`
  - explicit `radar-qmlp-cpu-profile.riscv` and `radar-qmlp-cpu-profile.bringup.o` rules
  - `radar-qmlp-cpu-profile.riscv` in `bringup-binaries`
- A pre-edit Makefile diff backup was written under `docs/backups/before_xradar_phase0_makefile_profile_*.patch`.

Validation:

```bash
source /home/soooarr/anaconda3/etc/profile.d/conda.sh
conda activate /home/soooarr/chipyard/.conda-env
make -C tests -B radar-qmlp-cpu-profile.riscv
```

Result:

- Build passed.
- Linker warning observed: `radar-qmlp-cpu-profile.riscv has a LOAD segment with RWX permissions`. This matches the current bare-metal style and was not treated as a new blocker.

Next board command when UART is available:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --bin tests/radar-qmlp-cpu-profile.riscv \
  --log-name phase0-radar-qmlp-cpu-profile-2026-06-07
```

Next implementation target after the CPU profile run:

- Add a dedicated MMIO/polling instrumentation path for QMLP DMA profiling without changing normal validation helper semantics.

## Checkpoint 2026-06-07 Offline Xradar Artifacts

Since board UART was not available, offline `Xradar` work continued without claiming board-level speedup.

New artifacts:

- `tests/radar_xradar_fallback.h`
- `tests/radar-xradar-fallback-host.c`
- `docs/riscv_xradar_isa_spec_2026-06-07.md`
- `docs/performance/xradar_offline_static_analysis_2026-06-07.md`

Makefile additions:

- `HOSTCC ?= gcc`
- `make -C tests xradar-host-test`

Offline validation:

```bash
make -C tests xradar-host-test
```

Result:

```text
[XRADAR-FALLBACK] counts rqdot4=848 scalar_tail_macs=64 rqscale8=96 total_macs=3456 packed_mac_coverage_x100=9814
[XRADAR-FALLBACK] PASSED
```

Interpretation:

- `rqdot4` can cover `3392 / 3456 = 98.14%` of current QMLP MAC terms statically, leaving only the 64 L1 tail MACs as scalar fallback.
- `rqscale8` covers the 96 hidden-layer fixed-point scale/ReLU/clamp operations.
- The software fallback is bit-exact against the scalar QMLP reference and packaged golden for the current 8-case test set.
- This supports keeping `rqdot4` and `rqscale8` as first-class candidates, but it still does not prove dynamic cycle share, RoCC speedup, execute-stage timing feasibility, `racc.*` usefulness, or Gemmini competitiveness.

Updated next offline target:

- Add a dedicated QMLP DMA MMIO/polling profile wrapper so `racc.*` can be evaluated later without modifying normal validation helper semantics.

## Checkpoint 2026-06-07 Offline Task Closure

Additional offline artifacts:

- `tests/radar-xradar-static-model-host.c`
- `tests/radar-axi-dma-qmlp-mmio-profile.c`

Additional Makefile targets:

```bash
make -C tests xradar-static-model
make -C tests xradar-host-test
```

RISC-V MMIO/polling profile build:

```bash
source /home/soooarr/anaconda3/etc/profile.d/conda.sh
conda activate /home/soooarr/chipyard/.conda-env
make -C tests -B radar-axi-dma-qmlp-mmio-profile.riscv
```

Result:

- Build passed.
- Linker warning observed: `radar-axi-dma-qmlp-mmio-profile.riscv has a LOAD segment with RWX permissions`.

Static model result:

```text
[XRADAR-STATIC] total_macs=3456 rqdot4=848 packed_terms=3392 tail_macs=64 packed_coverage_x100=9814 rqscale8=96
[XRADAR-AMDAHL] f_pct=40 sk2x_x1000=1250 sk4x_x1000=1429 sk6x_x1000=1500 sk8x_x1000=1538
[XRADAR-AMDAHL] f_pct=70 sk2x_x1000=1538 sk4x_x1000=2105 sk6x_x1000=2400 sk8x_x1000=2581
```

MMIO profile size:

```text
text=34964 data=16 bss=0 tests/radar-axi-dma-qmlp-mmio-profile.riscv
```

Archived disassembly:

- `logs/radar_nexysvideo/runtime/feature21-frequency-limit-2026-06-06/phase0-xradar-baseline-gate-2026-06-06/objdump-radar-axi-dma-qmlp-mmio-profile-2026-06-07.txt`

Board commands now queued:

```bash
scripts/run_nexysvideo_uart_tsi.sh \
  --bin tests/radar-qmlp-cpu-profile.riscv \
  --log-name phase0-radar-qmlp-cpu-profile-2026-06-07

scripts/run_nexysvideo_uart_tsi.sh \
  --bin tests/radar-axi-dma-qmlp-mmio-profile.riscv \
  --log-name phase0-qmlp-mmio-profile-2026-06-07
```

Offline status:

- QMLP arithmetic semantics and static model are complete enough for an offline ISA draft.
- `racc.*` measurement wrapper is built and ready for future board access.
- No RoCC/Rocket RTL should be started until the two queued board profiles or an explicit instruction-count-only thesis decision selects the first implementation path.
